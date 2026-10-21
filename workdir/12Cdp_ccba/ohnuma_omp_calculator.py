#!/usr/bin/env python3
"""Ohnuma optical-potential calculator for 12C(d,p)13C.

Run the Tkinter GUI: python3 ohnuma_omp_calculator.py
Run without a GUI:  python3 ohnuma_omp_calculator.py --cli --beam 16 --ex 7.688
Supply a known exit relative energy: --cli --ecm 8.7481

No third-party packages. The GUI requires Python's Tkinter module.

Sources:
  H. Ohnuma et al., Nucl. Phys. A448 (1986) 205-220, Table 1, p. 208.
  https://doi.org/10.1016/0375-9474(86)90087-4
  Q_gs = 2.7218 MeV: TUNL A=13 evaluation, reaction 28, p. 28.
  https://nucldata.tunl.duke.edu/nucldata/fas/13_1991.pdf
  FRESCO POT syntax: https://www.fresco.org.uk/input3.4/fresco-namelist-manual/node8.html

Kinematics are nonrelativistic. Default entrance masses are mass numbers
(m_d=2, m_12C=12); replace them with the masses used in your FRESCO card
to match its entrance energy. Q_gs is independently editable for the same
reason. Ex is the FINAL 13C excitation relative to its ground state.

E_in = m_12C/(m_d+m_12C) * E_d,lab
E_out = E_in + Q_gs - Ex
The p+13C column of Table 1 uses E_out: total relative kinetic energy of
the outgoing pair, not the proton's share of the CM kinetic energy and
not its angle-dependent laboratory energy. No Coulomb energy subtraction.

The emitted block uses TARGET-ONLY radii, R=r*A_target**(1/3), explicitly
setting AP=0 in POT TYPE=0. Tabulated strengths are copied directly,
including the spin-orbit strength, into standard FRESCO TYPE=3. The table
image does not specify its full spin-orbit operator; no independent
normalization conversion is inferred from the image.

The optional d+12C block copies the fixed 30-MeV-study parameters; it is
not an energy-dependent deuteron parameterization or a refit at 16 MeV.
Neutron-core binding potentials and collective couplings are not generated.
"""

import argparse
import math
from pathlib import Path

PARAMETERS = (
    ("V0", "MeV", "63.1 - 0.3 Ecm", 63.1, -0.3),
    ("r0", "fm", "1.15 - 0.001 Ecm", 1.15, -0.001),
    ("a", "fm", "0.57", 0.57, 0.0),
    ("WD", "MeV", "10.37 - 0.06 Ecm", 10.37, -0.06),
    ("rD", "fm", "1.15 - 0.001 Ecm", 1.15, -0.001),
    ("aD", "fm", "0.5", 0.5, 0.0),
    ("Vs.o.", "MeV", "5.5", 5.5, 0.0),
    ("rs.o.", "fm", "1.15 - 0.001 Ecm", 1.15, -0.001),
    ("as.o.", "fm", "0.57", 0.57, 0.0),
    ("rc", "fm", "1.15 - 0.001 Ecm", 1.15, -0.001),
)


def finite(value, name):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")
    return value


def positive_integer(value, name):
    value = finite(value, name)
    if value < 1 or not value.is_integer():
        raise ValueError(f"{name} must be a positive integer.")
    return int(value)


def calculate(beam=16.0, ex=3.089, qgs=2.7218, md=2.0, mc12=12.0,
              ecm=None, mode="CCBA"):
    """Evaluate the proton OMP and fixed deuteron reference parameters."""
    mode = mode.upper()
    if mode not in {"CCBA", "DWBA"}:
        raise ValueError("Mode must be CCBA or DWBA.")
    if ecm is None:
        beam, ex, qgs, md, mc12 = [finite(v, n) for v, n in
            zip((beam, ex, qgs, md, mc12), ("Beam energy", "Ex", "Q_gs", "m_d", "m_12C"))]
        if beam <= 0 or md <= 0 or mc12 <= 0:
            raise ValueError("Beam energy and entrance masses must be positive.")
        if ex < 0:
            raise ValueError("Ex must be nonnegative.")
        ein = beam * mc12 / (md + mc12)
        eout = ein + qgs - ex
        info = dict(beam=beam, ex=ex, qgs=qgs, md=md, mc12=mc12, ein=ein,
                    energy_source="Reaction kinematics")
    else:
        eout = finite(ecm, "Exit Ecm")
        info = dict(energy_source="Direct exit Ecm input")
    if eout <= 0:
        raise ValueError("The exit channel must be open: Ecm,out must be positive.")
    proton = {name: offset + slope * eout for name, _, _, offset, slope in PARAMETERS}
    if any(value <= 0 for value in proton.values()):
        raise ValueError("An OMP parameter is nonpositive at this energy; check the input.")
    deuteron = dict(zip((r[0] for r in PARAMETERS),
                       (110.7, 0.9, 0.801, 6.0 if mode == "CCBA" else 9.2,
                        1.42, 0.794, 9.32, 0.9, 0.551, 1.3)))
    return dict(info, eout=eout, proton=proton, deuteron=deuteron, mode=mode)


def summary(result):
    lines = ["12C(d,p)13C: Ohnuma Table 1", result["energy_source"]]
    if "ein" in result:
        lines += [f"E_d,lab = {result['beam']:.6f} MeV    Ex(13C) = {result['ex']:.6f} MeV",
                  f"m_d = {result['md']:g}    m_12C = {result['mc12']:g}    Q_gs = {result['qgs']:.6f} MeV",
                  f"Ecm,in  = {result['ein']:.6f} MeV"]
    lines += [f"Ecm,out = {result['eout']:.6f} MeV  <-- energy used in proton equations", "",
              f"{'Parameter':<12}{'p + 13C':>13}{'Unit':>8}    {'Equation':<25}"]
    for name, unit, equation, _, _ in PARAMETERS:
        lines.append(f"{name:<12}{result['proton'][name]:>13.6f}{unit:>8}    {equation}")
    lines += ["", "FRESCO radii: target-only R = r * A_target^(1/3).",
              "Spin-orbit: direct table strengths in standard FRESCO TYPE=3.",
              f"Optional d+12C reference: WD = {result['deuteron']['WD']:.1f} MeV ({result['mode']}).",
              "The deuteron reference is fixed to Table 1; it is not refitted at the entered beam energy."]
    return "\n".join(lines)


def potential_block(p, kp, at, label):
    return f"""! {label}; target-only radius scaling R = r * {at}**(1/3)
&POT kp={kp} type=0 p(1:3)={at:.6f} 0.000000 {p['rc']:.6f} /
! Real volume; no imaginary volume term in Table 1
&POT kp={kp} type=1 shape=0
     p(1:6)={p['V0']:.6f} {p['r0']:.6f} {p['a']:.6f}
             0.000000 {p['r0']:.6f} {p['a']:.6f} /
! Imaginary surface derivative; WD is the standard FRESCO TYPE=2 strength
&POT kp={kp} type=2 shape=0
     p(1:6)=0.000000 {p['rD']:.6f} {p['aD']:.6f}
             {p['WD']:.6f} {p['rD']:.6f} {p['aD']:.6f} /
! Projectile spin-orbit; table strength copied directly
&POT kp={kp} type=3 shape=0
     p(1:6)={p['Vs.o.']:.6f} {p['rs.o.']:.6f} {p['as.o.']:.6f}
             0.000000 {p['rs.o.']:.6f} {p['as.o.']:.6f} /
"""


def fresco_block(result, kp_p=2, kp_d=1, include_d=False):
    kp_p = positive_integer(kp_p, "Proton kp")
    kp_d = positive_integer(kp_d, "Deuteron kp")
    if include_d and kp_p == kp_d:
        raise ValueError("Proton and deuteron potentials need distinct kp indices.")
    header = ("! H. Ohnuma et al., NPA448 (1986) 205, Table 1, p.208\n"
              "! DOI: 10.1016/0375-9474(86)90087-4\n"
              f"! p+13C OMP evaluated at Ecm,out = {result['eout']:.6f} MeV\n")
    if "ein" in result:
        header += (f"! Ed,lab={result['beam']:.6f}; Ex={result['ex']:.6f}; Qgs={result['qgs']:.6f} MeV\n"
                   f"! Ecm,in={result['ein']:.6f}; Ecm,out=Ecm,in+Qgs-Ex\n")
    header += "! AP=0 below defines radius scaling only, not projectile kinematic mass.\n"
    if include_d:
        header += "! Fixed deuteron reference from the 30-MeV study; no beam-energy refit.\n"
        header += potential_block(result['deuteron'], kp_d, 12, f"d + 12C, {result['mode']}") + "\n"
    return header + potential_block(result['proton'], kp_p, 13, "p + 13C exit OMP")


def launch_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog

    class OhnumaApp(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Ohnuma 12C(d,p)13C OMP Calculator")
            self.geometry("1080x860")
            self.minsize(940, 700)
            outer = ttk.Frame(self, padding=12)
            outer.pack(fill="both", expand=True)
            ttk.Label(outer, text="Ohnuma optical-potential calculator", font=("TkDefaultFont", 15, "bold")).pack(anchor="w")
            ttk.Label(outer, text="12C(d,p)13C: the proton OMP uses the exit-channel relative energy.").pack(anchor="w", pady=(2, 8))
            inp = ttk.LabelFrame(outer, text="Channel energy inputs (MeV)", padding=8)
            inp.pack(fill="x")
            self.vars = {key: tk.StringVar(value=val) for key, val in
                         {"beam":"16.0", "ex":"3.089", "qgs":"2.7218", "md":"2", "mc12":"12", "ecm":"", "kp_p":"2", "kp_d":"1", "mode":"CCBA"}.items()}
            fields = [("beam","Ed,lab"),("ex","Ex(13C)"),("qgs","Q_gs"),("md","m_d"),("mc12","m_12C"),("ecm","Direct exit Ecm")]
            for col,(key,label) in enumerate(fields):
                ttk.Label(inp,text=label).grid(row=0,column=col,sticky="w",padx=4)
                if key == "ex":
                    widget = ttk.Combobox(inp,textvariable=self.vars[key],values=("0", "3.089", "6.86", "7.688", "8.22", "9.50", "9.90", "10.75", "10.82"),width=12)
                else:
                    widget = ttk.Entry(inp,textvariable=self.vars[key],width=14)
                widget.grid(row=1,column=col,sticky="ew",padx=4,pady=4)
                inp.columnconfigure(col,weight=1)
            ttk.Label(inp,text="Blank direct Ecm: calculate from reaction. A direct value overrides beam, Ex, Q and masses.").grid(row=2,column=0,columnspan=6,sticky="w",pady=4)
            ttk.Label(inp,text="Default masses 2 and 12 are the mass-number approximation. Match your FRESCO masses/Q if needed.").grid(row=3,column=0,columnspan=6,sticky="w")
            options = ttk.Frame(outer)
            options.pack(fill="x",pady=8)
            self.include_d = tk.BooleanVar(value=False)
            ttk.Checkbutton(options,text="Include fixed d+12C reference",variable=self.include_d).pack(side="left")
            for key,label in (("kp_p","Proton kp"),("kp_d","Deuteron kp")):
                ttk.Label(options,text=label).pack(side="left",padx=(12,4))
                ttk.Entry(options,textvariable=self.vars[key],width=5).pack(side="left")
            ttk.Label(options,text="Deuteron WD").pack(side="left",padx=(12,4))
            ttk.Combobox(options,textvariable=self.vars['mode'],values=("CCBA","DWBA"),state="readonly",width=7).pack(side="left")
            buttons = ttk.Frame(outer)
            buttons.pack(fill="x",pady=(0,8))
            for label,callback in (("Calculate",self.refresh),("Copy FRESCO block",self.copy_block),("Save FRESCO block",self.save_block),("About energies",self.about)):
                ttk.Button(buttons,text=label,command=callback).pack(side="left",padx=(0,8))
            notebook = ttk.Notebook(outer)
            notebook.pack(fill="both",expand=True)
            self.texts = {}
            for key,title in (("summary","Results and equations"),("block","FRESCO potential block")):
                frame=ttk.Frame(notebook)
                notebook.add(frame,text=title)
                text=tk.Text(frame,wrap="none",font=("TkFixedFont",10))
                scroll=ttk.Scrollbar(frame,orient="vertical",command=text.yview)
                horizontal=ttk.Scrollbar(frame,orient="horizontal",command=text.xview)
                text.configure(yscrollcommand=scroll.set,xscrollcommand=horizontal.set)
                text.grid(row=0,column=0,sticky="nsew")
                scroll.grid(row=0,column=1,sticky="ns")
                horizontal.grid(row=1,column=0,sticky="ew")
                frame.rowconfigure(0,weight=1)
                frame.columnconfigure(0,weight=1)
                self.texts[key]=text
            self.status=ttk.Label(outer,text="")
            self.status.pack(anchor="w",pady=(6,0))
            self.bind("<Return>",lambda event:self.refresh())
            self.refresh()

        def refresh(self):
            try:
                direct=self.vars['ecm'].get().strip()
                inputs={key:self.vars[key].get() for key in ("beam","ex","qgs","md","mc12")}
                result=calculate(**inputs,ecm=direct or None,mode=self.vars['mode'].get())
                block=fresco_block(result,self.vars['kp_p'].get(),self.vars['kp_d'].get(),self.include_d.get())
                for key,value in (("summary",summary(result)),("block",block)):
                    text=self.texts[key]
                    text.configure(state="normal")
                    text.delete("1.0","end")
                    text.insert("1.0",value)
                    text.configure(state="disabled")
                self.last_block=block
                self.status.configure(text=f"Proton equations evaluated at Ecm,out = {result['eout']:.6f} MeV.")
                return True
            except ValueError as exc:
                self.last_block=None
                self.status.configure(text="Input error. Correct inputs before copying or saving.")
                for text in self.texts.values():
                    text.configure(state="normal")
                    text.delete("1.0","end")
                    text.configure(state="disabled")
                messagebox.showerror("Ohnuma input error",str(exc))
                return False

        def copy_block(self):
            if self.refresh():
                self.clipboard_clear()
                self.clipboard_append(self.last_block)
                self.update()
                self.status.configure(text="FRESCO block copied.")

        def save_block(self):
            if not self.refresh():
                return
            filename=filedialog.asksaveasfilename(defaultextension=".nin",initialfile="ohnuma_p13C_potentials.nin",filetypes=(("FRESCO input","*.nin"),("Text","*.txt"),("All files","*")))
            if filename:
                try:
                    Path(filename).write_text(self.last_block,encoding="utf-8")
                    self.status.configure(text="FRESCO block saved.")
                except OSError as exc:
                    messagebox.showerror("Save error",str(exc))

        def about(self):
            messagebox.showinfo("Which energy?",
                "Ecm,in = m_12C/(m_d+m_12C) * Ed,lab\n"
                "Ecm,out = Ecm,in + Q_gs - Ex(13C)\n\n"
                "Use Ecm,out in the p+13C equations. It is the relative kinetic energy of the outgoing pair. "
                "Do not use Ed,lab, proton-only CM kinetic energy, or the detected proton laboratory energy.\n\n"
                "Ex is the final 13C excitation, even for transfer through the excited 12C core. "
                "An intermediate core excitation is not subtracted again.\n\n"
                "FRESCO block: target-only radii, direct table spin-orbit strengths. "
                "The table image alone does not define its spin-orbit operator normalization.\n\n"
                "The optional deuteron block uses fixed Table 1 values. CCBA/DWBA changes only its WD (6.0/9.2). "
                "No neutron-core binding potential or collective couplings are generated.")

    OhnumaApp().mainloop()


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cli',action='store_true',help='Print results and FRESCO block without opening a GUI.')
    for flag,default,helptext in (
        ('beam',16.0,'Deuteron laboratory energy (MeV).'),('ex',3.089,'Final 13C excitation (MeV).'),
        ('qgs',2.7218,'Ground-state reaction Q (MeV).'),('md',2.0,'Entrance deuteron mass.'),
        ('mc12',12.0,'Entrance 12C mass in the same units.'),('ecm',None,'Direct exit relative energy (MeV), overriding reaction inputs.')):
        parser.add_argument('--'+flag,type=float,default=default,help=helptext)
    parser.add_argument('--mode',choices=('CCBA','DWBA'),default='CCBA')
    parser.add_argument('--kp-p',type=int,default=2)
    parser.add_argument('--kp-d',type=int,default=1)
    parser.add_argument('--include-d',action='store_true',help='Also emit the fixed deuteron reference block.')
    parser.add_argument('--output',type=Path,help='Save the potential block to this file in CLI mode.')
    args=parser.parse_args()
    if not args.cli:
        if any(arg != default for arg,default in ((args.beam,16.0),(args.ex,3.089),(args.qgs,2.7218),(args.md,2.0),(args.mc12,12.0),(args.ecm,None),(args.mode,'CCBA'),(args.kp_p,2),(args.kp_d,1),(args.include_d,False),(args.output,None))):
            parser.error('Use --cli with command-line calculation options. GUI fields can be edited after launch.')
        launch_gui()
        return
    try:
        result=calculate(args.beam,args.ex,args.qgs,args.md,args.mc12,args.ecm,args.mode)
        block=fresco_block(result,args.kp_p,args.kp_d,args.include_d)
        print(summary(result)+'\n\n'+block)
        if args.output:
            args.output.write_text(block,encoding='utf-8')
    except (ValueError,OSError) as exc:
        parser.error(str(exc))


if __name__=='__main__':
    main()
