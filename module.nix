{ pkgs, lib, config, ... }: let
  cfg = config.programs.aicha;
in {
  options.programs.aicha = {
    enable = lib.mkEnableOption { description = "Enable Aicha chatbot"; };

    model = lib.mkOption {
      description = "Name of the LLM model to use";
      type = lib.types.str;
      default = "hermes";
    };

    dataDir = lib.mkOption {
      description = "Where to store Aicha data";
      type = lib.types.str;
      default = "$HOME/.aicha";
    };
  };

  config = {
    environment.systemPackages = lib.mkIf cfg.enable [
      (pkgs.callPackage ./package.nix {
        inherit pkgs;
        python = pkgs.python312;

        model = cfg.model;
        chat_dir = "${cfg.dataDir}/chat_history";
        model_dir = "${cfg.dataDir}/models";
      })
    ];
  };
}
