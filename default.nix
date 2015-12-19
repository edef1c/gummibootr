{ config, lib, pkgs, ... }:

with lib;

let
  cfg = config.boot.loader.gummibootr;

  efi = config.boot.loader.efi;

  gummibootBuilder = pkgs.substituteAll {
    src = ./gummiboot-builder.py;

    isExecutable = true;

    inherit (pkgs) python gummiboot binutils sbsigntool;

    nix = config.nix.package;

    timeout = if cfg.timeout != null then cfg.timeout else "";

    inherit (efi) efiSysMountPoint canTouchEfiVariables;

    efiArch = if stdenv.system == "x86_64-linux" then "x64"
         else if stdenv.system == "i686-linux" then "ia32"
         else throw "Unsupported system: ${stdenv.system}";
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
