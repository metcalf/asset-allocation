Installing numpy on my M1 mac required:
```
brew install openblas gfortran
export OPENBLAS=/opt/homebrew/opt/openblas/lib/
pipenv install
pipenv run pip install Cython pybind11
pipenv run pip install numpy --no-binary :all: --no-use-pep517
pipenv run pip install scipy --no-binary :all: --no-use-pep517
pipenv install
```
