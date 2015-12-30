#! @python@/bin/python
import argparse
import os
import errno
import subprocess
import glob
import tempfile

system_dir = lambda generation: "/nix/var/nix/profiles/system-%d-link" % (generation)
entry_file = lambda generation: "@efiSysMountPoint@/efi/linux/nixos-generation-%d.efi" % (generation)

def db_sign(src, dst):
    tmp = "%s.signed" % (dst)
    subprocess.check_call([
        "@sbsigntool@/bin/sbsign",
        "--key",  "/etc/uefi/DB.key",
        "--cert", "/etc/uefi/DB.crt",
        src, "--output", tmp
    ])
    os.rename(tmp, dst)

def add_entry(generation):
    entry_file = "@efiSysMountPoint@/efi/linux/nixos-generation-%d.efi" % (generation)
    generation_dir = os.readlink(system_dir(generation))
    tmp_path = "%s.tmp" % (entry_file)
    kernel_params = "systemConfig=%s init=%s/init " % (generation_dir, generation_dir)
    with open("%s/kernel-params" % (generation_dir)) as params_file:
        kernel_params += params_file.read()
    with tempfile.NamedTemporaryFile() as f_kernel_params, tempfile.NamedTemporaryFile() as f_os_release:
        print >> f_kernel_params, kernel_params
        f_kernel_params.flush()

        print >> f_os_release, 'ID="nixos"'
        print >> f_os_release, 'VERSION_ID="generation-%d"' % (generation)
        print >> f_os_release, 'PRETTY_NAME="NixOS Generation %d"' % (generation)
        f_os_release.flush()

        subprocess.check_call([
            "@binutils@/bin/objcopy",
            "--add-section", ".osrel=%s"         % f_os_release.name,    "--change-section-vma", ".osrel=0x20000",
            "--add-section", ".cmdline=%s"       % f_kernel_params.name, "--change-section-vma", ".cmdline=0x30000",
            "--add-section", ".linux=%s/kernel"  % generation_dir,       "--change-section-vma", ".linux=0x40000",
            "--add-section", ".initrd=%s/initrd" % generation_dir,       "--change-section-vma", ".initrd=0x3000000",
            "@gummiboot@/lib/gummiboot/linux@efiArch@.efi.stub", tmp_path
        ])
    subprocess.check_call(["@binutils@/bin/strip", tmp_path])
    try:
        db_sign(tmp_path, entry_file)
    finally:
        os.unlink(tmp_path)

def write_loader_conf(generation):
    with open("@efiSysMountPoint@/loader/loader.conf.tmp", 'w') as f:
        if "@timeout@" != "":
            print >> f, "timeout @timeout@"
        print >> f, "default nixos-generation-%d" % (generation)
    os.rename("@efiSysMountPoint@/loader/loader.conf.tmp", "@efiSysMountPoint@/loader/loader.conf")

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(path):
            raise

def get_generations(profile):
    gen_list = subprocess.check_output([
        "@nix@/bin/nix-env",
        "--list-generations",
        "-p",
        "/nix/var/nix/profiles/%s" % (profile),
        "--option", "build-users-group", ""
        ])
    gen_lines = gen_list.split('\n')
    gen_lines.pop()
    return [ int(line.split()[0]) for line in gen_lines ]

parser = argparse.ArgumentParser(description='Update NixOS-related gummiboot files')
parser.add_argument('default_config', metavar='DEFAULT-CONFIG', help='The default NixOS config to boot')
args = parser.parse_args()

mkdir_p("@efiSysMountPoint@/efi/boot")
db_sign("@gummiboot@/lib/gummiboot/gummiboot@efiArch@.efi", "@efiSysMountPoint@/efi/boot/boot@efiArch@.efi")

mkdir_p("@efiSysMountPoint@/efi/linux")
mkdir_p("@efiSysMountPoint@/loader")

gens = get_generations("system")
live = map(entry_file, gens)
dead = set(glob.iglob("@efiSysMountPoint@/efi/linux/nixos-generation-[1-9]*.efi")) - set(live)
for path in dead:
    os.unlink(path)
for gen in gens:
    add_entry(gen)
    if os.readlink(system_dir(gen)) == args.default_config:
        write_loader_conf(gen)
