import os

filepath = r"c:\Users\radhe\OneDrive\Documents\AI_Self-adaptive_Chip\Self Adaptability\SA_PoC_FPGA_Radheshyam\New_IEEEtran_how-to.tex"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# The new reference to append
new_ref = r"""\bibitem{sota_sst}
M.~Kossel \textit{et al.}, ``A T-Coil-Enhanced 8.5 Gb/s High-Swing SST Transmitter in 65 nm Bulk CMOS With $<$ $-$16 dB Return Loss Over 10 GHz Bandwidth,'' \textit{IEEE J. Solid-State Circuits}, vol.~43, no.~12, pp.~2905--2920, Dec.~2008.

"""

# Inject new reference before \end{thebibliography}
if "\\end{thebibliography}" in content and "sota_sst" not in content:
    content = content.replace("\\end{thebibliography}", new_ref + "\\end{thebibliography}")

# We need to replace the old table with the new table that includes 3 reference columns
old_table = r"""\begin{tabular}{lccc}
\toprule
\textbf{Metric} & \textbf{\cite{sota_pam4}} & \textbf{\cite{sota_tdzq}} & \textbf{This Work} \\
\midrule
\textbf{Technology} & 65-nm CMOS & 65-nm CMOS & \textbf{28-nm CMOS} \\
\textbf{Method} & Analog 3-Point ZQ & Time-Domain ZQ & \textbf{Digital ML DT} \\
\textbf{Error Rate} & N/A & 0.7\% (Avg) & \textbf{0.73\% (Max)} \\
\textbf{Area ($\text{mm}^2$)} & 0.0333 (Total) & 0.041 (Calib only) & \textbf{TBD$^\ast$} \\
\textbf{Multipliers} & N/A & N/A & \textbf{0} \\
\textbf{Reconfigurable} & No & No & \textbf{Yes (10.6\,KB SRAM)} \\
\bottomrule
\multicolumn{4}{l}{\footnotesize $^\ast$Post-layout ASIC synthesis area to be reported in future work.}
\end{tabular}"""

new_table = r"""\begin{tabular}{lcccc}
\toprule
\textbf{Metric} & \textbf{\cite{sota_sst}} & \textbf{\cite{sota_pam4}} & \textbf{\cite{sota_tdzq}} & \textbf{This Work} \\
\midrule
\textbf{Technology} & 65-nm CMOS & 65-nm CMOS & 65-nm CMOS & \textbf{28-nm CMOS} \\
\textbf{Method} & Analog SST Tuning & Analog 3-Point ZQ & Time-Domain ZQ & \textbf{Digital ML DT} \\
\textbf{Error Rate} & $<$-16dB RL & N/A & 0.7\% (Avg) & \textbf{0.73\% (Max)} \\
\textbf{Area ($\text{mm}^2$)} & 0.0648 (Total) & 0.0333 (Total) & 0.041 (Calib only) & \textbf{TBD$^\ast$} \\
\textbf{Multipliers} & N/A & N/A & N/A & \textbf{0} \\
\textbf{Reconfigurable} & No & No & No & \textbf{Yes (10.6\,KB SRAM)} \\
\bottomrule
\multicolumn{5}{l}{\footnotesize $^\ast$Post-layout ASIC synthesis area to be reported in future work.}
\end{tabular}"""

if old_table in content:
    content = content.replace(old_table, new_table)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Table updated with 3rd reference.")
