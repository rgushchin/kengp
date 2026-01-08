{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    naersk = {
      url = "github:nix-community/naersk";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    flake-utils.url = "github:numtide/flake-utils";
    self.submodules = true;
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      ...
    }@inputs:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        naersk = pkgs.callPackage inputs.naersk { };
        lib = pkgs.lib;
      in
      {
        formatter = pkgs.nixfmt-tree;
        packages = rec {
          semcode = naersk.buildPackage {
            src = ./semcode;
            nativeBuildInputs = [ pkgs.protobuf ];
            buildInputs = [ pkgs.libclang ];
          };

          ai-review = pkgs.stdenv.mkDerivation {
            name = "ai-review";
            src = ./.;

            nativeBuildInputs = [ pkgs.makeWrapper ];
            buildInputs = [ pkgs.python3 ];

            installPhase = ''
              mkdir -p $out/bin
              cp ai_review.py $out/bin/ai-review
              chmod +x $out/bin/ai-review
              wrapProgram $out/bin/ai-review --prefix PATH ${lib.makeBinPath [ semcode ]}
            '';
          };

          default = self.packages.${system}.ai-review;
        };
      }
    );
}
