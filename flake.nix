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
    aicha = import ./package.nix pkgs.python312Packages;
  in {
    packages.default = aicha;
    apps.default = inputs.flake-utils.lib.mkApp { drv = aicha; };
    devShells.default = pkgs.mkShell aicha;
  });
}
