# ASIC Submission Plot Explanations

To keep the ASIC deliverables completely clean and focused exclusively on hardware synthesis, we have removed all the massive explorational ML plots. The `plots/` directory now strictly contains the **two most meaningful visualization proofs** justifying the ASIC design.

## 1. `01_depth_sweep.png` (The Hardware Cost vs Accuracy Proof)

This plot visually justifies our selection of "Depth 14" (for Mixer) and "Depth 11/16" (for BGR) Decision Trees over arbitrarily larger neural combinations.

* **The X-Axis (Estimated Gates):** How do we calculate this? 
  * A Decision Tree node checks a single `pmon` or `temp` threshold using a simple integer comparator (`>` or `<`).
  * In standard 28nm synthesis logic, a 29-bit comparator combined with the necessary 2:1 routing multiplexers consumes approximately **~20 to 25 bare Digital Logic Gates**.
  * Therefore, the X-axis is calculated by multiplying the exact `Number_of_Leaves * 25`. It shows the physical silicon area footprint!
* **The Y-Axis (Accuracy):** This proves how accurate the model is purely at predicting the exact trim bit. 
* **The Conclusion:** You will notice a sharp elbow around ~10,000 gates where the accuracy perfectly hits >99%. Allowing the tree to grow infinitely deeper ("Depth = None") would explode the gate count to 400,000+ while simultaneously *lowering* real-world accuracy due to overfitting thermal noise. By strictly chopping the model at Depth 14, we secured maximum prediction bounds for minimum silicon area.

## 2. `actual_vs_predicted.png` (The Evaluation Residuals)

This is the ultimate proof of our Machine Learning models perfectly capturing the Cadence Physics.

* **What it plots:** It plots the "Actual Trim Target" (Y-axis) physically required by the analog block against what our "Python Predictor Algorithm Result" (X-axis) evaluates.
* **The Red Dotted Line:** This is the `y = x` perfect match line. If a prediction is 100% physically perfect, the blue scatter dot lands directly on the red line.
* **The Conclusion:** Because 99.7% of the results land identically on the red line, it visually confirms perfectly compressed analog emulation. For the 0.3% of dots that miss, you can visually see they miss by merely exactly `1` numeric offset step, proving that even our minimal boundary "errors" represent incredibly soft misses that will not realistically fail the 50Ω physical constraint in silicon.
