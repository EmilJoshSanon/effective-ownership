# Effective ownership

### Introduction

This repo is a showcasing of how the effective ownership in complex ownership structures can be calculated.

### Methodology

Since the size of the tree and the number of branches is arbitrary, a recursive function is used to generalise the algorithm.
When there are circular ownerships in the tree, an ownership matrix is created with dummy variables containing the residual ownership for each company with circular ownership. The matrix is then squared, the result matrix is squared again, and so on, until the result matrix is stable to two decimal points.

### Data

The data is real data fetched from the Danish company register, CVR.

### Prerequisites

- have poetry and python installed

### To install:

```bash
poetry install --no-root
```

### To run:

```bash
poetry run python main.py
```

Results has already been calculated and saved in the result folder.
