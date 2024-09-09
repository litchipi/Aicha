{
  inputs = {
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
      config = { allowUnfree = true; };
    };

    python_version = pkgs.python312;
    pythonpkg = python_version.withPackages (p: with p; [
      pip
      gpt4all-bindings
    ]);

    name = "my_script";
    deps = [
      pythonpkg
    ];

    start = pkgs.writeShellApplication {
      inherit name;
      runtimeInputs = deps;
      text = ''
        export PYTHONPATH="${pythonpkg}/${pythonpkg.sitePackages}";
        export LD_LIBRARY_PATH=${pkgs.gpt4all}/lib:$LD_LIBRARY_PATH
        ${pythonpkg}/bin/python -W ignore ./chat.py
      '';
    };
  in {
    packages.default = start;
    apps = {
      default = {
        type = "app";
        program = "${start}/bin/${name}";
      };
    };

    devShells.default = pkgs.mkShell {
      buildInputs = deps;
      PYTHONPATH = "${pythonpkg}/${pythonpkg.sitePackages}:$PYTHONPATH";
      LD_LIBRARY_PATH = "${pkgs.stdenv.cc.cc.lib}/lib:/run/opengl-driver/lib$LD_LIBRARY_PATH";
    };
  });
}
