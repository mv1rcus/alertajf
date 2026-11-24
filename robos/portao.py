"""Portão: imprime chove=true/false (para o GitHub Actions) conforme a chuva em JF."""
import os
import common as c
r = c.esta_chovendo()
print("chove=" + str(r).lower())
if os.environ.get("GITHUB_OUTPUT"):
    open(os.environ["GITHUB_OUTPUT"], "a").write("chove=" + str(r).lower() + "\n")
