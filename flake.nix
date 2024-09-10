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
    lib = pkgs.lib;

    nomic = python.pkgs.buildPythonPackage rec {
      pname = "nomic";
      version = "3.1.2";
      src = pkgs.fetchFromGitHub {
        owner = "nomic-ai";
        repo = "nomic";
        rev = "v${version}";
        sha256 = "sha256-cyd6Jvd/n/YpXkt6MctwdFSu3NEg63+HQM0brQn4rmI=";
      };

      nativeBuildInputs = with python.pkgs; [
        setuptools
        wheel
      ];

      propagatedBuildInputs = with python.pkgs; [
        loguru rich requests numpy pandas pydantic tqdm pyarrow pillow pyjwt
        click jsonlines
      ];

      pyproject=true;
    };

    python = pkgs.python312;
    pypkg = python.withPackages (p: with p; [
      gpt4all-bindings
      nomic
      numpy
      scikit-learn
      pdfminer-six
    ]);
    libs = with pkgs; [ gpt4all ];
    deps = [
    ];

    mkScript = name: cmd: pkgs.writeShellApplication {
      inherit name;
      runtimeInputs = [ pypkg ] ++ deps;
      text = ''
        export PYTHONPATH="${pypkg}/${pypkg.sitePackages}"
        export LD_LIBRARY_PATH=${lib.makeLibraryPath libs}:$$LD_LIBRARY_PATH
        ${pypkg}/bin/python -W ignore ${cmd}
      '';
    };

    aicha_deriv = { model ? "hermes", model_dir ? ".model", chat_dir ? ".chat" }:
      mkScript "aicha" "${./aicha.py} ${model} ${model_dir} ${chat_dir}";

    rag_deriv = {}: mkScript "rag" "${./rag.py}";
  in rec {
    packages.default = packages.aicha;
    apps.default = apps.aicha;
    devShells.default = pkgs.mkShell {
      buildInputs = [ pypkg ] ++ deps;
      PYTHONPATH = "${pypkg}/${pypkg.sitePackages}";
      LD_LIBRARY_PATH = "${lib.makeLibraryPath libs}:$$LD_LIBRARY_PATH";
    };

    packages.aicha = pkgs.callPackage aicha_deriv { };
    apps.aicha = { type = "app"; program = "${packages.aicha}/bin/aicha"; };

    packages.rag = pkgs.callPackage rag_deriv { };
    apps.rag = { type = "app"; program = "${packages.rag}/bin/rag"; };

    # TODO Enable and test once PR 340717 is merged
    # nixosModules.default = import ./module.nix;
  });
}
