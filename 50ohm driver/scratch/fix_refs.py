import os

filepath = r"c:\Users\radhe\OneDrive\Documents\AI_Self-adaptive_Chip\Self Adaptability\SA_PoC_FPGA_Radheshyam\New_IEEEtran_how-to.tex"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

refs_latex = r"""\bibitem{sota_pam4}
Y.-U. Jeong \textit{et al.}, ``A 0.64-pJ/Bit 28-Gb/s/Pin High-Linearity Single-Ended PAM-4 Transmitter With an Impedance-Matched Driver and Three-Point ZQ Calibration for Memory Interface,'' \textit{IEEE J. Solid-State Circuits}, vol.~56, no.~4, pp.~1278--1287, Apr.~2021.

\bibitem{sota_tdzq}
J.~Yun \textit{et al.}, ``A Single-Ended Impedance-Matched Transmitter With Single Ring-Oscillator-Based Time-Domain ZQ Calibration for Memory Interfaces,'' \textit{IEEE J. Solid-State Circuits}, vol.~59, no.~9, pp.~2971--2982, Sep.~2024.

"""

if "sota_pam4" not in content:
    content = content.replace("\\end{thebibliography}", refs_latex + "\\end{thebibliography}")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed references.")
