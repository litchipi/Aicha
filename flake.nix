{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-24.05"; #unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = inputs: inputs.flake-utils.lib.eachDefaultSystem (system: let
    pkgs = import inputs.nixpkgs {
      inherit system;
      config = { allowUnfree = true; };
    };

    python_version = pkgs.python311;
    pythonpkg = python_version.withPackages (p: with p; [
      pip
      requests
      tqdm
    ]);

    gpt4all-backend = pkgs.stdenv.mkDerivation {
      pname = "gpt4all-backend";
      inherit (pkgs.gpt4all) src version cmakeFlags nativeBuildInputs buildInputs;

      sourceRoot = "${pkgs.gpt4all.src.name}/gpt4all-backend";
      installPhase = ''
        cp -r ./ $out
      '';
    };

    gpt4all-bindings = pythonpkg.pkgs.buildPythonPackage {
      pname = "gpt4all-bindings";
      inherit (pkgs.gpt4all) src version;
      sourceRoot = "${pkgs.gpt4all.src.name}/gpt4all-bindings/python";
      pyproject = false;
      
      build-system = with pythonpkg.pkgs; [
        setuptools
        wheel
      ];

      patchPhase = ''
        substituteInPlace setup.py \
          --replace-fail 'SRC_CLIB_DIRECTORY = ' 'SRC_CLIB_DIRECTORY = "${gpt4all-backend.src}/gpt4all-backend" #' \
          --replace-fail 'SRC_CLIB_BUILD_DIRECTORY = ' 'SRC_CLIB_BUILD_DIRECTORY = "${gpt4all-backend}/" #' \
          --replace-fail 'DEST_CLIB_BUILD_DIRECTORY = ' 'DEST_CLIB_BUILD_DIRECTORY = os.path.join(DEST_CLIB_DIRECTORY, "build") #' \
          --replace-fail 'shutil.copy2' 'if "examples" in s: continue; print(s, "->", d); shutil.copy2'
          # --replace-fail 'DEST_CLIB_DIRECTORY = ' 'DEST_CLIB_DIRECTORY = os.path.join("/build/libfiles") #' \
      '';

      installPhase = ''
        ls -lha gpt4all
      '';

      postInstall = ''
        ls -lha $out
        cp -r llmodel_DO_NOT_MODIFY $out/lib/python3.11/site-packages/gpt4all/llmodel_DO_NOT_MODIFY
      '';
    };

    name = "my_script";
    deps = [
      pythonpkg
      pkgs.git-lfs
      gpt4all-bindings
    ];

    start = pkgs.writeShellApplication {
      inherit name;
      runtimeInputs = deps;
      text = ''
        if ! [ -d .model ]; then
          echo "[*] Getting model"
          git clone https://huggingface.co/NousResearch/Nous-Hermes-2-Mistral-7B-DPO .model
          cd .model
          git lfs install
          git lfs pull
          cd ..
        fi
        export PYTHONPATH="${pythonpkg}/${pythonpkg.sitePackages}:$PYTHONPATH";
        export LD_LIBRARY_PATH=${pkgs.gpt4all}/lib:$LD_LIBRARY_PATH
        ${pythonpkg}/bin/python -W ignore ./chat.py
      '';
    };
  in {
    packages.default = start;
    packages.gpt4all = gpt4all-bindings;
    packages.gpt4all-backend = gpt4all-backend;
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
