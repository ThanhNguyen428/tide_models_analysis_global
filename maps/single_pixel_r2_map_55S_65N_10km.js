/**
 * single_pixel_r2_map_55S_65N_10km.js
 *
 * 1,210,272 single-pixel SWOT coastline points (no patch averaging, centre
 * within 10 km of land), 55S-65N - the unfiltered counterpart to the
 * ice-filtered map.
 *
 * Payload d{1,2,3}.js carries variances rather than standard deviations, so
 * the tooltip shows the signed delta plus square-rooted spreads.
 */
(function () {
  "use strict";

  TideDiscrepancyMap.build({
    payload: [D1, D2, D3],
    layout: TideMap.LAYOUTS.VAR_6,
    view: TideMap.VIEW_GLOBAL,
    radii: TideMap.RADII_DEFAULT,
    coordDigits: 2,
    detailRows: TideDiscrepancyMap.ROWS.deltaAndVariances,
    release: function () { D1 = null; D2 = null; D3 = null; }
  });
})();
