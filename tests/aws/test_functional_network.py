from avocado import Test
from avocado_cloud.app.aws import aws
from avocado_cloud.app.aws import NetworkInterface
import time
import decimal
import re
from avocado_cloud.utils import utils_lib


class NetworkTest(Test):
    '''
    :avocado: tags=network,acceptance,fulltest,outposts
    '''
    def _compare_num(self, num1, num2, expect_ratio, msg=None):
        act_ratio = 100 - decimal.Decimal(num1) / decimal.Decimal(num2) * 100
        self.assertGreaterEqual(
            expect_ratio,
            act_ratio,
            msg="%s perf result diff ratio over expect %s, actual %s" %
            (msg, expect_ratio, act_ratio))
        self.log.info(
            "%s perf result diff ratio is within expect %s, actual %s" %
            (msg, expect_ratio, act_ratio))

    def _iperf3_test(self):
        '''
        Run iperf3 test between two vms, for now, we only use iperf3 to make
        sure there is no exceptions during test. About detail performance
        evaluatation, we are doing it in other thread. Plan to import
        performance evaluatation later.
        '''
        iperf3_install = "sudo yum install -y iperf3"
        iperf3_server = "sudo iperf3 -s"
        self.log.info("vm2 iperf server private ip is %s" %
                      self.vm2.priviate_ip)
        iperf3_client = "sudo iperf3 -P 10 -c %s " % self.vm2.priviate_ip

        self.log.info("Install iperf3 on vm1 and vm2")
        output = self.session1.cmd_output(iperf3_install,
                                          timeout=self.ssh_wait_timeout)
        self.log.info("Installation output vm1 %s %s" %
                      (self.vm1.instance_id, output))
        output = self.session2.cmd_output(iperf3_install,
                                          timeout=self.ssh_wait_timeout)
        self.log.info("Installation output vm2 %s %s" %
                      (self.vm2.instance_id, output))

        self.log.info("Start iperf3 server on vm2 %s" % self.vm2.instance_id)
        # output = self.session2.cmd_output(
        #    iperf3_server, timeout=self.ssh_wait_timeout)
        self.log.info("CMD: %s" % iperf3_server)
        self.session2.session.sendline(iperf3_server)
        time.sleep(10)
        # if output == None:
        #    self.fail("Failed to start iperf3 server on vm2!")
        # else:
        #    self.log.info("Start iperf3 server on vm2 successfully!")

        self.log.info("Start iperf3 test on vm1 %s" % self.vm1.instance_id)
        self.log.info("CMD: %s" % iperf3_client)
        status, output = self.session1.cmd_status_output(
            iperf3_client, timeout=self.ssh_wait_timeout)
        if status == 0:
            self.log.info(
                "Start iperf3 test on vm1 successfully! \n Result: %s " %
                output)
        else:
            self.fail("Failed to run iperf3 test on vm1! \n Result: %s " %
                      output)
        for line in output.split("\n"):
            if 'sender' in line and 'SUM' in line:
                sender_ipv4 = line.split(' ')[line.split(' ').index('sec') + 5]
            elif 'receiver' in line and 'SUM' in line:
                receiver_ipv4 = line.split(' ')[line.split(' ').index('sec') +
                                                5]
        # read expected perf result from official annonce
        # 0 means moderate and will not check whether it is expected.
        # if it is lower than 30%, consider it as fail.
        expect_perf = self.params.get('net_perf', "*/instance_types/*")
        expect_ratio = 30
        if expect_perf == 0:
            self.log.info(
                "Network performance is moderate, no need to compare result!")
        else:
            self._compare_num(sender_ipv4,
                              expect_perf,
                              expect_ratio,
                              msg="Sender")
            self._compare_num(receiver_ipv4,
                              expect_perf,
                              expect_ratio,
                              msg="Receiver")

        return output

    def setUp(self):
        self.session = None
        self.session1 = None
        self.session2 = None
        self.vm = None
        self.vm1 = None
        self.vm2 = None
        self.snap = None

        self.ssh_wait_timeout = None
        aws.init_test(self, instance_index=0)
        self.vm1 = self.vm
        self.session1 = self.session
        if self.name.name.endswith("test_iperf_ipv4"):
            self.log.info("2 Nodes needed!")
            aws.init_test(self, instance_index=1)
            self.vm2 = self.vm
            self.session2 = self.session
        else:
            self.log.info("1 Node needed!")

    def test_mtu_min_set(self):
        '''
        :avocado: tags=test_mtu_min_set,fast_check,kernel
        description:
            os-tests Test set mtu with minimal, maximum and various values in RHEL on AWS. Linked case RHEL-111097.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_mtu_min_set"
        bugzilla_id: 
            1502554
        customer_case_id: 
            n/a
        maintainer: 
            xiliang
        case_priority:
            0
        case_component: 
            network
        key_steps:
            1. Launch an instance on AWS.
            2. Log into the instance via ssh and check the newwork driver used via command "$ sudo ethtool -i eth0".
            3. Change mtu setting to value between 0 and the minimal one via command like "$ sudo ifconfig eth0 mtu 50".
            4. Change mtu setting to value larger than the maximum one via command like "$ sudo ifconfig eth0 mtu 9711".
            5. Change mtu setting to vaule in range via command like "$ sudo ifconfig eth0 mtu 68", and check connection via ping command.
            6. Change mtu settings to minimal and maximum vaules, and check connection via ping command.
            7. Here are the mtu ranges for different network drivers on AWS.
               ena mtu range in 128~9216
               ixgbevf mtu range in 68~9710
               vif mtu range in 68~65535
        pass_criteria: 
            MTU should not be set to vaules smaller than minimal one or larger than maximum one in step 2 and 3 which will cause network problem.
            MTU vaules are set to minimal and maximum ones or between them in step 4 and 5, and network connect works well with these vaules.
        '''
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        aws.check_session(self)
        case_name = "os_tests.tests.test_network_test.TestNetworkTest.test_mtu_min_max_set"
        utils_lib.run_os_tests(self, case_name=case_name)

    def test_iperf_ipv4(self):
        '''
        :avocado: tags=test_iperf_ipv4
        description:
            Use iperf to test network bandwidth of RHEL on AWS. 
            For now, we only run iperf test and did not compare result with standard. 
            If there is big gap, please manuall run inside the same placement group.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_iperf_ipv4"
        bugzilla_id: 
            n/a
        customer_case_id: 
            n/a
        maintainer: 
            xiliang
        case_priority:
            0
        case_component: 
            network
        key_steps:
            1. Check the bandwidth in specs of the instance under test, if it is less than 40 Gbps, use iperf3 to do the test.
            2. Launch two instances on AWS, one is as the server and the other is as the client.
            3. Install iperf3 in both instances via command "$ sudo yum install -y iperf3".
            4. Start the iperf server in instance A via command "$ sudo iperf3 -s" and check the ip address of the server.
               Note You may need to change security settings to allow connection between 2 instances (--protocol tcp --port 5001).
            5. Run iperf tests from the client via command "$ sudo iperf3 -P 10 -c $PrivateIPOfServer".
            6. Check the SUM bandwidth in the results.
        pass_criteria: 
            The SUM bandwidth run with iperf3 should be close but no big gap to the bandwidth in instance specs. 
            No exception when running iperf3 in instance on AWS.
        '''
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        aws.check_session(self)
        perf_spec = self.params.get('net_perf', '*/instance_types/*')
        if int(perf_spec) > 40:
            self.cancel('Cancel case as iperf3 is not suitable for \
bandwidth higher than 40G')
        self._iperf3_test()

    def test_sriov_ixbgevf(self):
        '''
        :avocado: tags=test_sriov_ixbgevf,fast_check
        description:
            Test enhanced network type of SRIOV (ixgbevf driver) in RHEL on AWS. Linked case RHEL7-87119.
            Instances with ixgbevf driver include C3, C4, D2, I2, R3 and M4 (excluding m4.16xlarge).
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_sriov_ixbgevf"
        bugzilla_id: 
            n/a
        customer_case_id: 
            n/a
        maintainer: 
            xiliang
        case_priority:
            0
        case_component: 
            network
        key_steps:
            1. Launch an instance with ixgbevf driver on AWS.
            2. Connect the instance via ssh, and check the ixgbevf module is installed and loaded by default via command "$ sudo modinfo ixgbevf".
            3. Verify the ixgbevf module is being used on a particular interface via command "$ sudo ethtool -i eth0".
            4. Run iperf tests according to case test_iperf_ipv4 to check the bandwidth of network as specs (5 Gbit/s or 10 Gbit/s).
        pass_criteria: 
            The ixgbevf module is installed and loaded by default.
            The ixgbevf driver is used by the specified network interface.
        '''
        self.session1.connect(timeout=self.ssh_wait_timeout)
        if not self.name.name.endswith("test_cleanup"):
            self.session = self.session1
            aws.check_session(self)
        eth_cmd = "ethtool -i eth0"
        if self.params.get('ixgbevf', '*/instance_types/*') > 0:
            self.log.info("Configure shows this instance supports ixgbevf")
        else:
            utils_lib.run_cmd(self, eth_cmd, expect_ret=0, cancel_kw='ixgbevf')

        self.log.info("Trying to check sriov ixgbevf interface!")

        mod_cmd = "modinfo ixgbevf"

        self.log.info("Get eth0 module infomation: %s" % self.vm1.instance_id)
        status, output = self.session1.cmd_status_output(eth_cmd)
        if status > 0:
            self.fail("Failed to check eth0 status: cmd : %s output:%s" %
                      (eth_cmd, output))
        elif status == 0:
            if 'ixgbevf' in output:
                self.log.info("eth0 has ixgbevf loaded. cmd: %s result: %s" %
                              (eth_cmd, output))
            else:
                self.fail(
                    "eth0 does not have ixgbevf loaded. cmd : %s result:%s" %
                    (eth_cmd, output))
        self.log.info("Get ixgbevf module infomation: %s" %
                      self.vm1.instance_id)
        status, output = self.session1.cmd_status_output(mod_cmd)
        if status > 0:
            self.fail(
                "Failed to get ixgbevf module information: cmd : %s result:%s"
                % (eth_cmd, output))
        elif status == 0:
            self.log.info("Below is ixgbevf information. cmd: %s result: %s" %
                          (eth_cmd, output))

    def test_sriov_ena(self):
        '''
        :avocado: tags=test_sriov_ena,fast_check
        description:
            Test enhanced network type of ENA (Elastic Network Adapter) in RHEL on AWS. Linked case RHEL7-87117.
            Instances with ENA drivers include,
            R4, H1, m4.16xlarge,
            X1, X1e, X2gd,
            I3, I3en, 
            T3, T3a, T4g,
            C5, C5a, C5ad, C5d, C5n, 
            M5, M5a, M5ad, M5d, M5dn, M5n, M5zn,
            R5, R5a, R5ad, R5b, R5d, R5dn, R5n,
            A1, C6g, C6gd, C6gn, M6g, M6gd, R6g, R6gd, 
            F1, Inf1,
            D3, D3en,
            G3, G3s, G4ad, G4dn, 
            P2, P3, P3dn, P4d,
            Mac1, z1d and so on.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_sriov_ena"
        bugzilla_id: 
            n/a
        customer_case_id: 
            n/a
        maintainer: 
            xiliang
        case_priority:
            0
        case_component: 
            network
        key_steps:
            1. Launch an instance with ena drivers on AWS.
            2. Connect the instance via ssh, and check the ena module is installed and loaded by default via command "$ sudo modinfo ena".
            3. Verify the ena module is being used on a particular interface via command "$ sudo ethtool -i eth0".
            4. Check the dmesg info related to ena "$ sudo dmesg|grep -w ena".
            5. Run iperf tests according to case test_iperf_ipv4 to check the bandwidth of network as specs (5 Gbit/s to 100 Gbit/s).
        pass_criteria: 
            The ena module is installed and loaded by default.
            The ena driver is used by the specified network interface.
            There are no error/warning/failure/unsupported feature messages about ena, better to compare the output with privious version, make sure there isn't regression which doesn't display as error in message.
        '''
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        aws.check_session(self)
        eth_cmd = "ethtool -i eth0"
        if self.params.get('ena', '*/instance_types/*') > 0:
            self.log.info("Configure shows this instance supports ena")
        else:
            utils_lib.run_cmd(self, eth_cmd, expect_ret=0, cancel_kw='ena')

        self.log.info("Trying to check sriov ena interface!")

        mod_cmd = "modinfo ena"

        self.log.info("Get eth0 module infomation: %s" % self.vm1.instance_id)
        status, output = self.session1.cmd_status_output(eth_cmd)
        if status > 0:
            self.fail("Failed to check eth0 status: cmd : %s output:%s" %
                      (eth_cmd, output))
        elif status == 0:
            if 'ena' in output:
                self.log.info("eth0 has ena loaded. cmd: %s result: %s" %
                              (eth_cmd, output))
            else:
                self.fail("eth0 does not have ena loaded. cmd : %s result:%s" %
                          (eth_cmd, output))
        self.log.info("Get ena module infomation: %s" % self.vm1.instance_id)
        status, output = self.session1.cmd_status_output(mod_cmd)
        if status > 0:
            self.fail(
                "Failed to get ena module information: cmd : %s result:%s" %
                (eth_cmd, output))
        elif status == 0:
            self.log.info("Below is ena information. cmd: %s result: %s" %
                          (eth_cmd, output))

    def test_sriov_ena_dmesg(self):
        '''
        :avocado: tags=test_sriov_ena_dmesg,fast_check
        description:
            Check dmesg related to ENA (Elastic Network Adapter) driver in RHEL on AWS. Linked case RHEL7-87117.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_sriov_ena_dmesg"
        bugzilla_id: 
            n/a
        customer_case_id: 
            n/a
        maintainer: 
            xiliang
        case_priority:
            0
        case_component: 
            network
        key_steps:
            1. Launch an instance with ENA drivers (instance list refer to description in case test_sriov_ena) on AWS.
            2. Connect the instance via ssh, and verify the ena module is being used on a particular interface via command "$ sudo ethtool -i eth0".
            3. Check the dmesg info related to ena "$ sudo dmesg|grep -w ena".
        pass_criteria: 
            The ena driver is used by the specified network interface.
            There are no error/warning/failure/unsupported feature messages about ena, better to compare the output with privious version, make sure there isn't regression which doesn't display as error in message.
        '''
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        aws.check_session(self)
        cmd = "ethtool -i eth0"
        output = utils_lib.run_cmd(self, cmd, expect_ret=0)
        if "driver: ena" not in output:
            self.cancel("No ena driver found!")
        self.log.info("Trying to check sriov ena boot messages!")
        aws.check_dmesg(self, 'ena', match_word_exact=True)

    def test_sriov_ena_unload_load(self):
        '''
        :avocado: tags=test_sriov_ena_unload_load,fast_check,kernel
        description:
            Test unload and reload ENA (Elastic Network Adapter) module in RHEL on AWS.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_sriov_ena_unload_load"
        bugzilla_id: 
            n/a
        customer_case_id: 
            n/a
        maintainer: 
            xiliang
        case_priority:
            0
        case_component: 
            network
        key_steps:
            1. Launch an instance with ENA drivers (instance list refer to description in case test_sriov_ena) on AWS.
            2. Connect the instance via ssh, and verify the ena module is being used on a particular interface via command "$ sudo ethtool -i eth0".
            3. Unload and load ena moudle via command "$ sudo modprobe -r ena; sudo modprobe ena".
            4. Check the dmesg info related to ena "$ sudo dmesg|grep -w ena".
        pass_criteria: 
            The ena can be unloaded and loaded without error.
            There are no error/warning/failure/unsupported feature messages about ena.
        '''
        self.log.info("Test unload and load ena module")
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        aws.check_session(self)
        utils_lib.run_cmd(self, 'ethtool -i eth0', cancel_kw='ena')
        cmd_string = 'modprobe -r ena;modprobe ena'
        cmd = 'sudo echo "%s" >/tmp/mod.sh' % cmd_string
        utils_lib.run_cmd(self, cmd, expect_ret=0)
        cmd = 'sudo chmod 755 /tmp/mod.sh'
        utils_lib.run_cmd(self, cmd, expect_ret=0)
        cmd = 'sudo su'
        utils_lib.run_cmd(self, cmd, expect_ret=0)
        cmd = '/tmp/mod.sh'
        utils_lib.run_cmd(self, cmd, expect_ret=0)

        aws.check_dmesg(self, 'ena', match_word_exact=True)

    def test_xen_netfront_unload_load(self):
        '''
        :avocado: tags=test_xen_netfront_unload_load,fast_check
        description:
            Test unload and reload xen_netfront module in RHEL on AWS.
            Instances with xen_netfront dirver include T2 and G2.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_xen_netfront_unload_load"
        bugzilla_id: 
            n/a
        customer_case_id: 
            n/a
        maintainer: 
            xiliang
        case_priority:
            0
        case_component: 
            network
        key_steps:
            1. Launch an T2 or G2 instance on AWS.
            2. Connect the instance via ssh, and verify the xen_netfront module is being used on a particular interface via command "$ sudo ethtool -i eth0".
            3. Unload and load xen_netfront moudle via command "$ sudo modprobe -r xen_netfront; sudo modprobe xen_netfront".
            4. Check the dmesg info related to xen_netfront "$ sudo dmesg|grep -w ena".
        pass_criteria: 
            The xen_netfront can be unloaded and loaded without error.
            There are no error/warning/failure/unsupported feature messages about xen_netfront.
        '''
        self.log.info("Test unload and load xen_netfront module")
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        cmd = 'sudo ethtool -i eth0'
        output = utils_lib.run_cmd(self, cmd, msg='Check network driver!')
        if 'driver: vif' not in output:
            self.cancel('No xen_netfront used!')
        aws.check_session(self)
        cmd_string = 'modprobe -r xen_netfront;modprobe xen_netfront'
        cmd = 'sudo echo "%s" >/tmp/mod.sh' % cmd_string
        utils_lib.run_cmd(self, cmd, expect_ret=0)
        cmd = 'sudo chmod 755 /tmp/mod.sh'
        utils_lib.run_cmd(self, cmd, expect_ret=0)
        cmd = 'sudo su'
        utils_lib.run_cmd(self, cmd, expect_ret=0)
        cmd = '/tmp/mod.sh'
        utils_lib.run_cmd(self, cmd, expect_ret=0)

        aws.check_dmesg(self, 'xen_netfront', match_word_exact=True)

    def test_pci_reset(self):
        '''
        :avocado: tags=test_pci_reset
        description:
            [Skip] Test unload and reload xen_netfront module in RHEL on AWS.
            Skip this case since there is a CANTFIX bug 1687330 with this case.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_pci_reset"
        bugzilla_id: 
            n/a
        customer_case_id: 
            n/a
        maintainer: 
            xiliang
        case_priority:
            0
        case_component: 
            network
        key_steps:
            1. Launch an instance with ENA drivers (instance list refer to description in case test_sriov_ena) on AWS.
            2. Connect the instance via ssh, check the ena driver is used by NIC via command "$ sudo ethtool -i eth0".
            3. List PCI devices information via command "$ sudo lspci".
            4. Reset ena device via command "$ sudo echo 1 > /sys/devices/pci0000:00/0000:00:05.0/reset".
        pass_criteria: 
            PCI reset successfully.
            There are no error/warning/failure/unsupported feature messages about ena.
        '''
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        cmd = 'sudo lspci'
        utils_lib.run_cmd(self, cmd)
        self.cancel('Cancel this case as bug 1687330 which is TESTONLY!')
        cmd = 'sudo find /sys -name reset* -type f|grep pci'
        output = utils_lib.run_cmd(self, cmd)
        if 'reset' not in output:
            self.cancel("No pci support reset!")
        for pci_reset in output.split('\n'):
            cmd = 'sudo su'
            utils_lib.run_cmd(self, cmd)
            cmd = 'echo 1 > %s' % pci_reset
            utils_lib.run_cmd(self, cmd, expect_ret=0, timeout=120)
        aws.check_dmesg(self, 'fail')
        aws.check_dmesg(self, 'error')
        aws.check_dmesg(self, 'warn')
        cmd = 'dmesg'
        utils_lib.run_cmd(self, cmd, expect_ret=0, expect_not_kw='Call Trace')

    def test_ethtool_C_coalesce(self):
        '''
        :avocado: tags=test_ethtool_C_coalesce,fast_check
        description:
        Use ethtool to change the coalescing settings of the specified network device.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_ethtool_C_coalesce"
        bugzilla_id: 
            n/a
        customer_case_id: 
            n/a
        maintainer: 
            xiliang
        case_priority: 
            0
        case_component: 
            network
        key_steps:
            1. Launch an instance on AWS EC2.
            2. Use ethtool to query the specified network device for coalescing information via command "$ sudo ethtool -c  eth0".
            3. Use ethtool to change the coalescing settings via command "$ sudo ethtool -C eth0 rx-usecs 3".
            4. Change the coalescing settings to different vaules like 
            'stats-block-usecs', 'sample-interval', 'pkt-rate-low',
            'pkt-rate-high', 'rx-usecs', 'rx-frames', 'rx-usecs-irq',
            'rx-frames-irq', 'tx-usecs', 'tx-frames', 'tx-usecs-irq',
            'tx-frames-irq', 'rx-usecs-low', 'rx-frame-low', 'tx-usecs-low',
            'tx-frame-low', 'rx-usecs-high', 'rx-frame-high', 'tx-usecs-high',
            'tx-frame-high'.
        pass_criteria: 
            The coalescing setting can be change successfully, or if cannot be change, message like "Operation not permitted" should be reported.
            And no error, warning, call track or other exception in dmesg.
        '''
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        aws.check_session(self)
        cmd = ' sudo  ethtool -c eth0'
        utils_lib.run_cmd(self, cmd, msg='Show current settings.')
        cmd = "ethtool -C eth0  rx-usecs 3"
        output = utils_lib.run_cmd(self, cmd)
        if "Operation not supported" in output:
            self.cancel("Operation not supported!")
        if "Operation not permitted" in output:
            self.cancel("Operation not permitted")
        self.log.info("Trying to change coalesce")
        coalesce_list = [
            'stats-block-usecs', 'sample-interval', 'pkt-rate-low',
            'pkt-rate-high', 'rx-usecs', 'rx-frames', 'rx-usecs-irq',
            'rx-frames-irq', 'tx-usecs', 'tx-frames', 'tx-usecs-irq',
            'tx-frames-irq', 'rx-usecs-low', 'rx-frame-low', 'tx-usecs-low',
            'tx-frame-low', 'rx-usecs-high', 'rx-frame-high', 'tx-usecs-high',
            'tx-frame-high'
        ]

        for coalesce in coalesce_list:
            cmd = 'sudo ethtool -C eth0 %s 2' % coalesce
            utils_lib.run_cmd(self, cmd, expect_ret=0)
            cmd = 'sudo  ethtool -c eth0'
            utils_lib.run_cmd(self, cmd, expect_kw="%s: 2" % coalesce)
        cmd = 'dmesg|tail -20'
        utils_lib.run_cmd(self, cmd)

    def test_ethtool_G(self):
        '''
        :avocado: tags=test_ethtool_G,fast_check
        description:
            os-tests Use ethtool to change the rx/tx ring parameters of the specified network device.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_ethtool_G"
        bugzilla_id: 
            1722628
        customer_case_id: 
            n/a
        maintainer: 
            xiliang
        case_priority: 
            0
        case_component: 
            network
        key_steps:
            1. Launch an instance on AWS EC2.
            2. Use ethtool to check maximums and current rx/tx ring parameters via command "$ sudo ethtool -g  eth0".
            2. Use ethtool to change the rx/tx ring parameters via command "$ sudo ethtool -G eth0 rx 512 tx 512".
            3. Change the rx/tx ring parameters to maximums, minimal and invalid parameters e.g., -1.
            4. Check the rx/tx ring is changed via command "$ sudo ethtool -g eth0".
        pass_criteria: 
            The supported rx/tx ring parameters can be changed.
            Cannot set the ring parameters to -1.
            And no error, warning, call track or other exception in dmesg.
        '''
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        aws.check_session(self)
        case_name = "os_tests.tests.test_network_test.TestNetworkTest.test_ethtool_G"
        utils_lib.run_os_tests(self, case_name=case_name)

    def test_ethtool_S_xdp(self):
        '''
        :avocado: tags=test_ethtool_S_xdp,fast_check
        description:
            [RHEL8.5] os-tests Use ethtool to query the specified network device xdp statistics.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_ethtool_S_xdp"
        bugzilla_id: 
            1908542
        customer_case_id: 
            n/a
        maintainer: 
            xiliang
        case_priority: 
            0
        case_component: 
            network
        key_steps:
            1. Launch an instance on AWS EC2.
            2. Use ethtool to query the specified network device xdp statistics.
        pass_criteria: 
            Can read xdp statics from RHEL8.5.
            eg. # ethtool -S eth0 |grep xdp
                  queue_0_rx_xdp_aborted: 0
                  queue_0_rx_xdp_drop: 0
                  queue_0_rx_xdp_pass: 0
                  queue_0_rx_xdp_tx: 0
                  queue_0_rx_xdp_invalid: 0
                  queue_0_rx_xdp_redirect: 0

        '''
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        aws.check_session(self)
        case_name = "os_tests.tests.test_network_test.TestNetworkTest.test_ethtool_S_xdp"
        utils_lib.run_os_tests(self, case_name=case_name)

    def test_ethtool_K_offload(self):
        '''
        :avocado: tags=test_ethtool_K_offload,fast_check
        description:
            Test use ethtool to change the offload parameters and other features of the specified network device in RHEL on AWS.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_ethtool_K_offload"
        bugzilla_id: 
            n/a
        customer_case_id: 
            n/a
        maintainer: 
            xiliang
        case_priority: 
            0
        case_component: 
            network
        key_steps:
            1. Launch an instance on AWS EC2.
            2. Use command "$ sudo  ethtool -k eth0" to query currently state of protocol offload and other features.
            3. Use ethtool to turn off offload parameters and other features via command "$ sudo ethtool -K eth0 $feature off".
            4. Check currently state of offload and other features again.
            5. Use ethtool to turn on offload parameters and other features via command "$ sudo ethtool -K eth0 $feature on".
            6. Check currently state of offload and other features.
       pass_criteria: 
            Each offload and features could be turned off and turned on again, and no exception, warn, fail or call trace in dmesg.
        '''
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        aws.check_session(self)
        cmd = ' sudo  ethtool -k eth0'
        setting_out = utils_lib.run_cmd(self, cmd, msg='Show current settings.')
        cmd = 'sudo ethtool -i eth0'
        output = utils_lib.run_cmd(self, cmd, msg='Check network driver!')
        if 'driver: ena' in output:
            option_dict = {
                'tx': 'tx-checksumming',
                'sg': 'scatter-gather',
                'gso': 'generic-segmentation-offload',
                'gro': 'generic-receive-offload',
                'tx-nocache-copy': 'tx-nocache-copy',
                'rxhash': 'receive-hashing',
                'highdma': 'highdma'
            }
        elif 'driver: vif' in output:
            option_dict = {
                'sg': 'scatter-gather',
                'tso': 'tcp-segmentation-offload',
                'gso': 'generic-segmentation-offload',
                'gro': 'generic-receive-offload',
                'tx-nocache-copy': 'tx-nocache-copy'
            }
        else:
            option_dict = {
                'rx': 'rx-checksumming',
                'tx': 'tx-checksumming',
                'sg': 'scatter-gather',
                'tso': 'tcp-segmentation-offload',
                'gso': 'generic-segmentation-offload',
                'gro': 'generic-receive-offload',
                'tx-gre-segmentation': 'tx-gre-segmentation',
                'tx-nocache-copy': 'tx-nocache-copy',
                'tx-ipip-segmentation': 'tx-ipip-segmentation',
                'tx-sit-segmentation': 'tx-sit-segmentation',
                'tx-udp_tnl-segmentation': 'tx-udp_tnl-segmentation',
                'tx-gre-csum-segmentation': 'tx-gre-csum-segmentation',
                'tx-udp_tnl-csum-segmentation': 'tx-udp_tnl-csum-segmentation',
                'tx-gso-partial': 'tx-gso-partial'
            }

        for option in option_dict.keys():
            if option_dict[option] not in setting_out:
                continue
            cmd = 'sudo ethtool -K eth0 %s off' % option
            utils_lib.run_cmd(self, cmd)
            cmd = 'sudo ethtool -k eth0'
            utils_lib.run_cmd(self, cmd, expect_kw="%s: off" % option_dict[option])
            cmd = 'sudo ethtool -K eth0 %s on' % option
            utils_lib.run_cmd(self, cmd, expect_ret=0)
            cmd = 'sudo ethtool -k eth0'
            utils_lib.run_cmd(self, cmd, expect_kw="%s: on" % option_dict[option])

        cmd = 'dmesg|tail -20'
        utils_lib.run_cmd(self, cmd)
        aws.check_dmesg(self, 'fail')
        aws.check_dmesg(self, 'error')
        aws.check_dmesg(self, 'warn')
        cmd = 'dmesg'
        utils_lib.run_cmd(self, cmd, expect_ret=0, expect_not_kw='Call Trace')

    def test_ethtool_s_msglvl(self):
        '''
        :avocado: tags=test_ethtool_s_msglvl,fast_check
        description:
            Test use ethtool to change the driver message type flags in RHEL on AWS.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_ethtool_s_msglvl"
        bugzilla_id: 
            n/a
        customer_case_id: 
            n/a
        maintainer: 
            xiliang
        case_priority: 
            0
        case_component: 
            network
        key_steps:
            1. Launch an instance on AWS EC2.
            2. Use ethtool to disable all msglvl via command "$ sudo ethtool -s ethX msglvl 0".
            3. Change the driver message type to different vaules like 'drv', 'probe', 'link', 'timer', 'ifdown', 'ifup', 'rx_err', 'tx_err', 'tx_queued', 'intr', 'tx_done', 'rx_status', 'pktdata', 'hw', 'wol'.
               "$ sudo ethtool -s eth0 msglvl $type on"
               "$ sudo ethtool -s eth0 msglvl $type off"
            4. Check the message level after each change via command "$ sudo ethtool eth0".
       pass_criteria: 
            When all msglvl disabled, no message level name displays.
            The corresponding message level name displays when it's on.
        '''
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        aws.check_session(self)
        cmd = "ethtool eth0"
        output = utils_lib.run_cmd(self, cmd, expect_ret=0)
        if "Current message level" not in output:
            self.cancel("Operation not supported!")
        self.log.info("Trying to change msglvl")
        msglvl_list = [
            'drv', 'probe', 'link', 'timer', 'ifdown', 'ifup', 'rx_err',
            'tx_err', 'tx_queued', 'intr', 'tx_done', 'rx_status', 'pktdata',
            'hw', 'wol'
        ]
        cmd = 'sudo  ethtool -s eth0 msglvl 0'
        utils_lib.run_cmd(self, cmd, msg='Disable all msglvl for now!')
        for msglvl in msglvl_list:
            cmd = 'sudo ethtool -s eth0 msglvl %s on' % msglvl
            utils_lib.run_cmd(self, cmd, expect_ret=0)
            cmd = "sudo ethtool eth0"
            utils_lib.run_cmd(self, cmd, expect_kw=msglvl)

        for msglvl in msglvl_list:
            cmd = 'sudo ethtool -s eth0 msglvl %s off' % msglvl
            utils_lib.run_cmd(self, cmd, expect_ret=0)
            cmd = "sudo ethtool eth0|grep -v 'link modes'"
            utils_lib.run_cmd(self, cmd, expect_not_kw=msglvl)
        cmd = 'dmesg|tail -20'
        utils_lib.run_cmd(self, cmd)

    def test_ethtool_X(self):
        '''
        :avocado: tags=test_ethtool_X,fast_check
        description:
        Test using ethtool to change rxfh setting.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_ethtool_X"
        bugzilla_id: 
            1693098
        customer_case_id: 
            n/a
        maintainer: 
            xiliang
        case_priority: 
            0
        case_component: 
            network
        key_steps:
            1. Launch an instance on AWS EC2.
            2. Use ethtool to change rxfh setting via command "ethtool -X eth0 default".
            3. Check the output of this command and dmesg.
        pass_criteria: 
            "Operation not permitted" message should be reported but no ena fail message reported in dmesg.
            Since ena does not support reading this feature.
            $sudo ethtool -x eth0
            Cannot get RX flow hash indirection table: Operation not supported
        '''
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        aws.check_session(self)
        self.log.info("Test change rxfh setting.")
        cmd = "ethtool -x eth0"
        utils_lib.run_cmd(self, cmd, msg='Display setting before changing it.')
        cmd = "ethtool -X eth0 default"
        output = utils_lib.run_cmd(self, cmd)
        if "Operation not supported" in output:
            self.cancel("Operation not supported!")
        self.log.info("As bug 1693098, will not check return value for now.")
        # utils_lib.run_cmd(self, cmd, expect_ret=0,msg='Try to set rxfh with \
        # -X option.')
        utils_lib.run_cmd(self, cmd, msg='Try to set rxfh with -X option.')
        cmd = "ethtool -x eth0"
        utils_lib.run_cmd(self, cmd, msg='Display setting after changed it.')

    def test_ethtool_P(self):
        '''
        :avocado: tags=test_ethtool_P,fast_check
        description:
            os-tests Test using ethtool to query permanent address.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_ethtool_P"
        bugzilla_id: 
            1704435
        customer_case_id: 
            BZ1704435
        maintainer: 
            xiliang
        case_priority: 
            0
        case_component: 
            network
        key_steps:
            1. Launch an instance on AWS EC2.
            2. Use ethtool to query permanent address via command "$ sudo ethtool -P ethX".
            3. Check the output of this command.
        pass_criteria: 
            Actual permanent address should be shown, but not 00:00:00:00:00:00.
        '''
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        aws.check_session(self)
        case_name = "os_tests.tests.test_network_test.TestNetworkTest.test_ethtool_P"
        utils_lib.run_os_tests(self, case_name=case_name)

    def test_persistent_route(self):
        '''
        :avocado: tags=test_persistent_route,fast_check
        description:
            os-tests check if can add persistent static route.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_persistent_route"
        bugzilla_id: 
            1971527
        customer_case_id: 
            BZ1971527
        maintainer: 
            xiliang
        case_priority: 
            0
        case_component: 
            network
        key_steps:
            1. # nmcli connection modify 'System eth0' +ipv4.routes "10.8.8.0/24 10.7.9.5"
            2. # nmcli connection down 'System eth0';nmcli connection up 'System eth0'
            3. # ip r
        expected_result:
            New static route added.
            eg. 10.8.8.0/24 via 10.7.9.5 dev eth0 proto static metric 100
        '''
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        aws.check_session(self)
        case_name = "os_tests.tests.test_network_test.TestNetworkTest.test_persistent_route"
        utils_lib.run_os_tests(self, case_name=case_name)

    def test_network_hotplug(self):
        '''
        :avocado: tags=test_network_hotplug,fast_check
        description:
            Test hotplug network interface to RHEL on AWS. Linked case RHEL7-103904.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_network_hotplug"
        bugzilla_id: 
            n/a
        customer_case_id: 
            n/a
        maintainer: 
            xiliang
        case_priority: 
            0
        case_component: 
            network
        key_steps:
            1. Launch an instance on AWS EC2.
            2. Attach a network interface to the instance, check the network in guest, e.g., "$ sudo lspci", "$ sudo ip addr show".
            3. Detach the network interface from the instance, check the nework in guest again.
            4. Check dmesg log of the instance.
        pass_criteria: 
            When the second network interface is attached in step 2, there are 2 Elastic Network Adapters displays in PCI devices, and the IP address are auto assigned to the device.
            When the second network interface is detached in step 3, there are 1 Elastic Network Adapters displays in PCI devices, and only 1 NIC displays when showing ip information.
            No crash or panic in system, no related error message or call trace in dmesg.
        '''
        self.network = NetworkInterface(self.params)
        self.assertTrue(self.network.create(),
                        msg='network interface create failed!')
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        netdev_index = 1
        self.network.attach_to_instance(self.vm1.instance_id, netdev_index)
        for i in range(1, 4):
            time.sleep(5)
            self.log.info('Check network in guest, loop%s' % i)
            cmd = "lspci"
            output1 = utils_lib.run_cmd(self, cmd)
            cmd = "ip addr show"
            output1 = utils_lib.run_cmd(self, cmd)
            if 'eth%s' % netdev_index not in output1:
                self.log.info("Added nic not found")
        self.network.detach_from_instance(self.vm1.instance_id)
        time.sleep(5)
        cmd = "ip addr show"
        utils_lib.run_cmd(self, cmd)
        self.network.delete()
        self.assertIn('eth%d' % netdev_index,
                      output1,
                      msg='eth%d not found after attached nic' % netdev_index)
        cmd = 'dmesg'
        utils_lib.run_cmd(self, cmd, expect_not_kw='Call Trace')

    def test_second_ip_hotplug(self):
        '''
        :avocado: tags=test_second_ip_hotplug,fast_check
        description:
            [RHEL8.4] Test hotplug network interface to RHEL on AWS. Linked case RHEL7-103904.
        polarion_id:
            https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitems?query=title:"[AWS]NetworkTest.test_second_ip_hotplug"
        bugzilla_id: 
            1623084,1642461
        customer_case_id: 
            BZ1623084,BZ1642461
        maintainer: 
            xiliang
        case_priority: 
            0
        case_component: 
            network
        key_steps:
            1. Launch an instance on AWS EC2.
            2. Check if package NetworkManager-cloud-setup is installed via command "$ sudo rpm -q NetworkManager-cloud-setup", if not, use yum install to install it.
            3. Check the service status via command "$ sudo systemctl status nm-cloud-setup.timer".
            4. Assign the second IP to the NIC of instance.
            5. Check the ip address of the NIC for several times via command "$ sudo ip addr show eth0".
            6. Remove the second IP from the NIC of instance.
            7. Check if the second IP address is removed from the NIC.
        pass_criteria: 
            After the second IP is assigned to the NIC of instance in step 4, there will be 2 IP address shows in step5.
            After the second IP is removed from the NIC of instance 6, there will be only 1 IP address shows in the step7.
        '''
        self.session1.connect(timeout=self.ssh_wait_timeout)
        self.session = self.session1
        cmd = 'rpm -q NetworkManager-cloud-setup'
        utils_lib.run_cmd(self, cmd, cancel_not_kw='could not be found,not installed')
        cmd = 'sudo systemctl status nm-cloud-setup.timer'
        utils_lib.run_cmd(self, cmd)
        self.vm1.assign_new_ip()
        cmd = 'sudo ip addr show eth0'
        start_time = time.time()
        while True:
            out = utils_lib.run_cmd(self, cmd)
            if self.vm.another_ip in out:
                break
            end_time = time.time()
            if end_time - start_time > 330:
                cmd = 'sudo systemctl status nm-cloud-setup.timer'
                utils_lib.run_cmd(self, cmd)
                self.fail("expected 2nd ip {} not found in guest".format(self.vm.another_ip))
            time.sleep(25)
        cmd = 'sudo ip addr show eth0'
        start_time = time.time()
        self.vm1.remove_added_ip()
        while True:
            out = utils_lib.run_cmd(self, cmd)
            if self.vm.another_ip not in out:
                break
            end_time = time.time()
            if end_time - start_time > 330:
                cmd = 'sudo systemctl status nm-cloud-setup.timer'
                utils_lib.run_cmd(self, cmd)
                self.fail("expected 2nd ip {} not removed from guest".format(self.vm.another_ip))
            time.sleep(25)

    def tearDown(self):
        aws.done_test(self)
        if self.vm.is_created:
            self.session = self.session1
            if self.session.session.is_responsive(
            ) is not None and self.vm1.is_started():
                if self.name.name.endswith("test_pci_reset"):
                    cmd = 'sudo dmesg --clear'
                    utils_lib.run_cmd(self, cmd, msg='Clear dmesg')
                aws.gcov_get(self)
                aws.get_memleaks(self)
                self.session.close()
            self.session1.close()
            if self.name.name.endswith("test_iperf_ipv4"):
                self.session2.close()
