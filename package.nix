{ pkgs, python, model_dir, chat_dir }: let
  pythonpkg = python.withPackages (p: with p; [ gpt4all-bindings ]);
in pkgs.writeShellApplication {
  name = "aicha";
  runtimeInputs = [ pythonpkg ];

  text = ''
    export PYTHONPATH="${pythonpkg}/${pythonpkg.sitePackages}"
    export LD_LIBRARY_PATH=${pkgs.gpt4all}/lib:$LD_LIBRARY_PATH
    ${pythonpkg}/bin/python -W ignore ${./aicha.py} ${model_dir} ${chat_dir}
  '';
}
