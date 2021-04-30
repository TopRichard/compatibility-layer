import os
import reframe as rfm
import reframe.utility.sanity as sn


class RunInGentooPrefixTestError(rfm.core.exceptions.ReframeError):
    pass


class RunInGentooPrefixTest(rfm.RunOnlyRegressionTest):
    eessi_version = parameter(['2020.12', '2021.03'])
    eessi_arch = parameter(['aarch64', 'x86_64'])
    eessi_os = parameter(['linux'])
    eessi_repo_dir = '/cvmfs/pilot.eessi-hpc.org'

    def __init__(self):
        self.valid_systems = ['*']
        self.valid_prog_environs = ['*']
        self.compat_dir = os.path.join(
            self.eessi_repo_dir,
            self.eessi_version,
            'compat',
            self.eessi_os,
            self.eessi_arch,
        )
        self.executable = os.path.join(self.compat_dir, 'startprefix')
        self.command = None
        self.exit_code = sn.extractsingle(r'Leaving Gentoo Prefix with exit status (\d*)', self.stdout, 1, int)


    @rfm.run_before('run')
    def set_executable_opts(self):
        if not os.path.exists(self.executable):
            raise RunInGentooPrefixTestError(f'startprefix script cannot be found at: {self.executable}')
        if not self.command:
            raise RunInGentooPrefixTestError('No command specified that should be run inside the Gentoo Prefix environment!')

        self.executable_opts = ['<<<', f'"{self.command}"']


@rfm.simple_test
class EchoTest(RunInGentooPrefixTest):
    def __init__(self):
        super().__init__()
        self.descr = 'Verify that startprefix works by running an echo command'
        self.command = 'echo hello'
        self.sanity_patterns = sn.all([
            sn.assert_eq(self.exit_code, 0),
            sn.assert_found(r'hello', self.stdout),
        ])


@rfm.simple_test
class ToolsAvailableTest(RunInGentooPrefixTest):
    tool = parameter(['emerge', 'equery', 'archspec'])

    def __init__(self):
        super().__init__()
        self.descr = 'Verify that some required tools are available'
        self.command = f'which {self.tool}'
        self.sanity_patterns = sn.all([
            sn.assert_found(r'%s/.*/%s' % (self.compat_dir, self.tool), self.stdout),
        ])


@rfm.simple_test
class RunEmergeTest(RunInGentooPrefixTest):
    def __init__(self):
        super().__init__()
        self.descr = 'Verify that emerge can be run'
        self.command = 'emerge --version'
        self.sanity_patterns = sn.all([
            sn.assert_eq(self.exit_code, 0),
        ])


@rfm.simple_test
class RunEqueryTest(RunInGentooPrefixTest):
    def __init__(self):
        super().__init__()
        self.descr = 'Verify that equiry can be run'
        self.command = 'equery --version'
        self.sanity_patterns = sn.all([
            sn.assert_eq(self.exit_code, 0),
        ])


@rfm.simple_test
class ArchspecTest(RunInGentooPrefixTest):
    def __init__(self):
        self.skip_if(self.eessi_arch == 'ppc64le')
        super().__init__()
        self.descr = 'Verify that archspec can be run'
        self.command = 'archspec cpu'
        self.sanity_patterns = sn.all([
            sn.assert_eq(self.exit_code, 0),
        ])


@rfm.simple_test
class LmodTest(RunInGentooPrefixTest):
    def __init__(self):
        super().__init__()
        self.descr = 'Verify that Lmod can be used by running: module avail'
        if self.eessi_version.startswith('2020'):
            lmod_init = os.path.join(self.compat_dir, 'usr', 'lmod', 'lmod', 'init', 'profile')
        else:
            lmod_init = os.path.join(self.compat_dir, 'usr', 'share', 'Lmod', 'init', 'profile')
        self.command = f'source {lmod_init} && module avail'
        self.sanity_patterns = sn.all([
            sn.assert_eq(self.exit_code, 0),
            sn.assert_found(r'lmod\s+settarg', self.stderr),
            sn.assert_found(r'Use "module spider" to find all possible modules and extensions.', self.stderr),
        ])


@rfm.simple_test
class EessiSetTest(RunInGentooPrefixTest):
    def __init__(self):
        super().__init__()
        self.descr = 'Test whether a EESSI set is available for the given architecture, operating system, and version.'
        self.command = 'emerge --list-sets'
        my_eessi_set = f'eessi-{self.eessi_version}-{self.eessi_os}-{self.eessi_arch}'
        self.sanity_patterns = sn.all([
            sn.assert_eq(self.exit_code, 0),
            sn.assert_found(my_eessi_set, self.stdout),
        ])


@rfm.simple_test
class EessiSetInstalledTest(RunInGentooPrefixTest):
    def __init__(self):
        super().__init__()
        self.descr = 'Test whether a the packages of the EESSI set have been installed.'
        self.command = 'qlist -IRv'
        my_eessi_set = f'eessi-{self.eessi_version}-{self.eessi_os}-{self.eessi_arch}'
        set_path = os.path.join(self.compat_dir, 'etc', 'portage', 'sets', my_eessi_set)
        set_packages = []
        with open(set_path, 'r') as setfile:
            packages = setfile.read().strip().split('\n')
            if packages != ['']:
                set_packages = [package[1:] if package.startswith('=') else package for package in packages]

        self.sanity_patterns = sn.all([
            sn.assert_found(set_package, self.stdout) for set_package in set_packages
        ])


@rfm.simple_test
class Utf8LocaleTest(RunInGentooPrefixTest):
    def __init__(self):
        super().__init__()
        self.descr = 'Verify that the UTF-8 locale is available.'
        self.command = 'locale -a'
        self.sanity_patterns = sn.all([
            sn.assert_eq(self.exit_code, 0),
            sn.assert_found(r'\nen_US.utf8\n', self.stdout),
        ])


@rfm.simple_test
class SymlinksToHostFilesTest(RunInGentooPrefixTest):
    symlink_to_host = parameter([
        'etc/group',
        'etc/passwd',
        'etc/hosts',
        'etc/nsswitch.conf',
        'etc/resolv.conf',
        'lib64/libnss_centrifydc.so.2',
        'lib64/libnss_ldap.so.2',
        'lib64/libnss_sss.so.2',
    ])

    def __init__(self):
        # the etc/hosts symlink was added in 2021 versions
        self.skip_if(self.symlink_to_host == 'etc/hosts' and self.eessi_version.startswith('2020'))
        
        super().__init__()
        self.descr = 'Verify that all required symlinks to host files have been created.'
        symlink_path = os.path.join(self.compat_dir, self.symlink_to_host)
        self.command = f'readlink {symlink_path}'
        self.sanity_patterns = sn.all([
            sn.assert_eq(self.exit_code, 0),
            sn.assert_found(f'\n/{self.symlink_to_host}\n', self.stdout),
        ])
