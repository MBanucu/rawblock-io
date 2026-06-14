{
  description = "rawblock-io: Raw block device I/O with automatic strategy fallback";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    { self
    , nixpkgs
    , flake-utils
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ self.overlays.default ];
        };
      in
      {
        packages.default = pkgs.rawblock-io;

        devShells.default = pkgs.mkShell {
          inputsFrom = [ pkgs.rawblock-io ];
          packages = [ pkgs.python3 ];
          shellHook = ''
            echo "rawblock-io dev shell. Run tests:"
            echo "  python -m unittest discover -s tests -v"
          '';
        };
      }
    )
    // {
      overlays.default = final: prev: {
        rawblock-io = final.python3.pkgs.callPackage ./default.nix {
          src = final.lib.cleanSource ./.;
        };
      };
    };
}
