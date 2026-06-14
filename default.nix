{
  lib
, buildPythonPackage
, setuptools
, src
}:
buildPythonPackage rec {
  pname = "rawblock-io";
  version = "0.1.0";
  pyproject = true;

  inherit src;

  nativeBuildInputs = [ setuptools ];

  doCheck = false;
  pythonImportsCheck = [ "rawblock_io" ];

  meta = with lib; {
    description = "Raw block device I/O with automatic strategy fallback and cross-platform device/mount resolution";
    homepage = "https://github.com/MBanucu/rawblock-io";
    license = licenses.gpl3Only;
    maintainers = with maintainers; [ ];
  };
}
