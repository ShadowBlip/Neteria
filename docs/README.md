To regenerate:
`cd docs
rm -rf *.rst Makefile
sphinx-apidoc -H Neteria -e -F -o . ../neteria/
make clean
make html`
