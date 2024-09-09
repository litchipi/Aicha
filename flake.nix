{
  inputs = {
    # TODO  Remove once PR https://github.com/NixOS/nixpkgs/pull/340717 is merged
    fork.url = "github:litchipi/nixpkgs/gpt4all-bindings";
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = inputs: inputs.flake-utils.lib.eachDefaultSystem (system: let
    forkpkgs = import inputs.fork { inherit system; };
    pkgs = import inputs.nixpkgs {
      inherit system;
      overlays = [(self: super: {
        python312 = forkpkgs.python312;
        python312Packages = forkpkgs.python312Packages;
      })];
    };

    package = import ./package.nix {
      inherit pkgs;
      python = pkgs.python312;
      chat_dir = "/tmp/aicha/chat_history";
      model_dir = "/tmp/aicha/model";
    };

  in {
    packages.default = package;
    apps.default = { type = "app"; program = "${package}/bin/aicha"; };
    devShells.default = pkgs.mkShell package;
  });
}
