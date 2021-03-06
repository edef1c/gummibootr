{ config, lib, pkgs, ... }:

with lib;

let
  cfg = config.boot.loader.gummibootr;

  efi = config.boot.loader.efi;

  systemd = config.systemd.package;

  gummibootBuilder = pkgs.substituteAll {
    src = ./gummiboot-builder.py;

    isExecutable = true;

    inherit systemd;
    inherit (pkgs) python binutils sbsigntool;

    nix = config.nix.package.out;

    timeout = if cfg.timeout != null then cfg.timeout else "";

    inherit (efi) efiSysMountPoint;

    efiArch = if systemd.system == "x86_64-linux" then "x64"
         else if systemd.system == "i686-linux" then "ia32"
         else throw "Unsupported system: ${systemd.system}";
  };
in {
  options.boot.loader.gummibootr = {
    enable = mkOption {
      default = false;

      type = types.bool;

      description = "Whether to enable the gummiboot UEFI boot manager";
    };

    timeout = mkOption {
      default = if config.boot.loader.timeout == null then 10000 else config.boot.loader.timeout;

      example = 4;

      type = types.nullOr types.int;

      description = ''
        Timeout (in seconds) for how long to show the menu (null if none).
        Note that even with no timeout the menu can be forced if the space
        key is pressed during bootup
      '';
    };
  };

  config = mkIf cfg.enable {
    assertions = [
      {
        assertion = (config.boot.kernelPackages.kernel.features or { efiBootStub = true; }) ? efiBootStub;

        message = "This kernel does not support the EFI boot stub";
      }
      {
        assertion = !efi.canTouchEfiVariables;

        message = "This bootloader doesn't support fiddling with EFI variables";
      }
    ];

    boot.loader.grub.enable = mkDefault false;

    system = {
      build.installBootLoader = gummibootBuilder;

      boot.loader.id = "gummibootr";

      requiredKernelConfig = with config.lib.kernelConfig; [
        (isYes "EFI_STUB")
      ];
    };
  };
}
