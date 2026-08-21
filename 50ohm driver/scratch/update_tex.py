import os

filepath = r"c:\Users\radhe\OneDrive\Documents\AI_Self-adaptive_Chip\Self Adaptability\SA_PoC_FPGA_Radheshyam\New_IEEEtran_how-to.tex"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

table_latex = r"""\subsection{State-of-the-Art Comparison}
Table~\ref{tab:sota_comp} compares the proposed ML-based calibration with recent state-of-the-art transmitter impedance calibration techniques. Unlike traditional analog approaches~\cite{sota_pam4} or time-domain ring-oscillator calibrations~\cite{sota_tdzq}, the proposed purely digital Decision Tree engine requires zero multipliers and zero precision external components. By leveraging on-chip sensors and piecewise-constant modeling, the proposed design achieves competitive calibration accuracy (0.73\% maximum error vs. 0.7\% average error in~\cite{sota_tdzq}) while being highly portable across technology nodes due to its SRAM-based reconfigurable architecture.

\begin{table}[!t]
\caption{Comparison with State-of-the-Art Impedance Calibration\label{tab:sota_comp}}
\centering
\begin{tabular}{lccc}
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
\end{tabular}
\end{table}

"""

refs_latex = r"""\bibitem{sota_pam4}
Y.-U. Jeong \textit{et al.}, ``A 0.64-pJ/Bit 28-Gb/s/Pin High-Linearity Single-Ended PAM-4 Transmitter With an Impedance-Matched Driver and Three-Point ZQ Calibration for Memory Interface,'' \textit{IEEE J. Solid-State Circuits}, vol.~56, no.~4, pp.~1278--1287, Apr.~2021.

\bibitem{sota_tdzq}
J.~Yun \textit{et al.}, ``A Single-Ended Impedance-Matched Transmitter With Single Ring-Oscillator-Based Time-Domain ZQ Calibration for Memory Interfaces,'' \textit{IEEE J. Solid-State Circuits}, vol.~59, no.~9, pp.~2971--2982, Sep.~2024.

"""

# Insert table right before \subsection{Advantages}
if "\\subsection{Advantages}" in content and "\\subsection{State-of-the-Art Comparison}" not in content:
    content = content.replace("\\subsection{Advantages}", table_latex + "\\subsection{Advantages}")

# Insert refs right before \end{thebibliography}
if "\\end{thebibliography}" in content and "sota_pam4" not in content:
    content = content.replace("\\end{thebibliography}", refs_latex + "\\end{thebibliography}")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Modification complete.")
