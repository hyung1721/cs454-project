# Analysis on Software Metric Consistency

This repository contains the code used for the team project conducted under the theme **"Analysis on Software Metric Consistency"** as part of the **CS454: AI-Based Software Engineering** course at KAIST.
The project aimed to replicate [a prior study](https://dl.acm.org/doi/abs/10.1145/2372251.2372260) analyzing the consistency of cohesion metrics and extend the analysis to coupling metrics.

## Contributors (Team 6)
- **Donghwan Shin**
- **Sunwoo Kim**
- **Woojin Kim**
- **Shinyoung Lee**

## Project Overview
This project replicates the pipeline from [an existing research paper](https://dl.acm.org/doi/abs/10.1145/2372251.2372260) on cohesion metric consistency using Python and extends the analysis to coupling metrics. The key components of the project are:

### Files
- `main.py`  
  Implements the pipeline from [the original paper](https://dl.acm.org/doi/abs/10.1145/2372251.2372260), enabling the replication of the cohesion metric consistency analysis and providing tools to analyze the consistency of various metrics.

- `ga.py`  
  Implements a Genetic Algorithm (GA) pipeline to generate refactoring series that simultaneously improve multiple metrics based on the implemented pipelines.


### Results
You may check some results of our research in `/log`.
