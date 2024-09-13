pypkgs: pypkgs.buildPythonApplication {
  pname = "aicha";
  version = "0.0.1";
  src = ./.;
  pyproject=true;

  dependencies = with pypkgs; [
    numpy
    gpt4all
    scikit-learn
    pdfminer-six
  ];

  build-system = [ pypkgs.setuptools ];
}
