# tide_models_analysis_global
Analyzing tide predictions from FES and GOT across different coastal locations in the tropics

---
Install all Python dependencies for this repo using:

```
pip install -r requirements.txt
```
---

Data source: [SWOT Satellite, Expert Data, Version D](https://www.earthdata.nasa.gov/data/catalog/pocloud-swot-l2-lr-ssh-expert-d-d#documents-and-resources)

Variables used: 
* ssh_karin_2
* height_cor_xover
* ssh_karin_2_qual
* height_cor_xover_qual
* depth_and_elevation
* distance_to_coast
* ocean_tide_fes
* ocean_tide_got 

Across all available cycles for a given "valid" pixel,
the measured and modeled data are recorded to calculate the coefficient of determination
(R<sup>2</sup>) and the correlated variance of a given tide model and ssh_karin_2 + height_cor_xover.

The specific details also vary between bbounds of of analysis (see below).

<!-- 
## Patch analysis

Refer to `general_logic.txt` for the detailed logic driving the algorithm behind the patch analyses.

We consider two patch sizes in our analysis: patches of 5x5 pixels and patches of 10x10 pixels with center points located
within 5km of nearby coastline. The analysis was done from 25 N to 25 S.


* `r2_discrepancy_5x5.html`: contains the results of using 5x5 patches. Contains 315,602 "valid" patches.
* `r2_discrepancy_map.html`: contains the results of using 10x10 patches. Contains 344,595 "valid" patches. -->

---

## Single pixel analysis (all files located in `single_pixel_analysis/`)

Refer to `general_logic.txt` for the detailed logic driving the algorithm behind the single pixel analyses.

Our initial tropical-latitude (25 N to 25 S) analyses considered pixels within two distances from nearby coastline: 5km and 10km.

A third analysis expanded the latitude range from 65 N to 55 S and considered pixels within 10km from nearby coastline.

1. `single_pixel_r2_map_5km.html`: contains the results of single-pixel analysis within 5km of coastline. Contains 212,580 "valid" points.
2. `single_pixel_r2_map_10km.html`: contains the results of single-pixel analysis within 10km of coastline. Contains 456,794 "valid" points.
3. `single_pixel_r2_map_55S_65N_10km.html`: same as second map, but with expanded latitude bounds from 65 N to 55 S.
4. `single_pixel_r2_map_ice_filtered.html`: same as third map, but excluding pixels containing ice.
5. `multivariate_r2_map_ice_filtered.html`: a multivariate map that distinguishes pixels by which tide model, if any, best explains its relationship with SSH. Based on fourth map.