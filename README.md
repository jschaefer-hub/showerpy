# Overview  

**ShowerPy** is a set of Python classes that provides users with a simple interface to create single-shower CORSIKA simulations, extract full particle track information, and generate shower plots.  
![Shower Image](media/shower_plots.png)  

All data is available as pandas DataFrames, allowing you to create custom plots and perform detailed analysis.

# Getting Started  

First, create and activate the `showerpy` mamba environment using the following commands:
```shell 
mamba env create -f environment.yml
mamba activate showerpy
```
Then, open the demo notebook Demo.ipynb, which provides an introduction to using ShowerPy.

# Simulating Showers
As demonstrated in the demo notebook, the CorsikaRunner class is used to generate the required simulations.
If you are running the demo notebook on woodycap5 or woodycap6, the provided link to the CORSIKA executable points to a public installation, so no additional setup is required.