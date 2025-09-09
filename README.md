# Effective ownership

### Introduction

This repo is a showcasing of how the effective ownership in complex ownership structures can be calculated.

### Methodology

Unless a company owns 100% of another company, the ownership is given in interval form (e.g. 5-10%, <5%). This creates a problem when in some cases the upper limit of the interval is not possible due to the sum of the lower limits of the remaining branches exceeding the residual ownership (e.g. upper limit = 20% and sum of lower limits = 40% + 45% = 85%). In such cases, the upper limit is set to 100% - sum of residual lower limits.

In cases where the ownership is expressed as <x% (e.g. <5%), the lower limit is set to 0.01%

Since the size of the tree and the number of branches is arbitrary, a recursive function is used to generalise the algorithm.

When there are circular ownerships in the tree, an ownership matrix is created with dummy variables containing the residual ownership for each company with circular ownership. The matrix is then squared, the result matrix is squared again, and so on, until the result matrix is stable to three decimal points. Since we have no way of knowing how the dummy variables distribute over other owners of one of the companies in a curcular ownership, we use the lower limit of the interval to calculate the effective ownership and multiplies that with the relative [upper limit]/[lower limit] to get the upper limit of the effective ownership.

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
