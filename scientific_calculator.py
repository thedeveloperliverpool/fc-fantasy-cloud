import ast
import math
import tkinter as tk
from tkinter import ttk


# --- Safe expression evaluator ---
class SafeEvaluator(ast.NodeVisitor):
    ALLOWED_BINOPS = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.Pow: lambda a, b: a ** b,
        ast.Mod: lambda a, b: a % b,
        ast.FloorDiv: lambda a, b: a // b,
    }

    ALLOWED_UNARYOPS = {
        ast.UAdd: lambda a: +a,
        ast.USub: lambda a: -a,
    }

    def __init__(self, use_degrees=False):
        self.use_degrees = use_degrees
        self.functions = {
            "sin": self._sin,
            "cos": self._cos,
            "tan": self._tan,
            "asin": self._asin,
            "acos": self._acos,
            "atan": self._atan,
            "sqrt": math.sqrt,
            "log": math.log10,
            "ln": math.log,
            "exp": math.exp,
            "abs": abs,
            "floor": math.floor,
            "ceil": math.ceil,
            "round": round,
            "fact": self._fact,
        }
        self.constants = {
            "pi": math.pi,
            "e": math.e,
        }

    def _to_rad(self, x):
        return math.radians(x) if self.use_degrees else x

    def _from_rad(self, x):
        return math.degrees(x) if self.use_degrees else x

    def _sin(self, x):
        return math.sin(self._to_rad(x))

    def _cos(self, x):
        return math.cos(self._to_rad(x))

    def _tan(self, x):
        return math.tan(self._to_rad(x))

    def _asin(self, x):
        return self._from_rad(math.asin(x))

    def _acos(self, x):
        return self._from_rad(math.acos(x))

    def _atan(self, x):
        return self._from_rad(math.atan(x))

    def _fact(self, x):
        if x < 0 or int(x) != x:
            raise ValueError("factorial only defined for non-negative integers")
        return math.factorial(int(x))

    def visit(self, node):
        return super().visit(node)

    def visit_Expression(self, node):
        return self.visit(node.body)

    def visit_BinOp(self, node):
        op_type = type(node.op)
        if op_type not in self.ALLOWED_BINOPS:
            raise ValueError("unsupported operator")
        left = self.visit(node.left)
        right = self.visit(node.right)
        return self.ALLOWED_BINOPS[op_type](left, right)

    def visit_UnaryOp(self, node):
        op_type = type(node.op)
        if op_type not in self.ALLOWED_UNARYOPS:
            raise ValueError("unsupported operator")
        operand = self.visit(node.operand)
        return self.ALLOWED_UNARYOPS[op_type](operand)

    def visit_Call(self, node):
        if not isinstance(node.func, ast.Name):
            raise ValueError("invalid function")
        func_name = node.func.id
        if func_name not in self.functions:
            raise ValueError("unknown function")
        args = [self.visit(arg) for arg in node.args]
        return self.functions[func_name](*args)

    def visit_Name(self, node):
        if node.id in self.constants:
            return self.constants[node.id]
        raise ValueError("unknown identifier")

    def visit_Num(self, node):
        return node.n

    def visit_Constant(self, node):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("invalid constant")

    def generic_visit(self, node):
        raise ValueError("invalid expression")


def safe_eval(expr, use_degrees=False):
    expr = expr.replace("^", "**")
    tree = ast.parse(expr, mode="eval")
    evaluator = SafeEvaluator(use_degrees=use_degrees)
    return evaluator.visit(tree)


# --- UI ---
class CalculatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Scientific Calculator")
        self.geometry("420x600")
        self.resizable(False, False)

        self.use_degrees = tk.BooleanVar(value=False)
        self.expr_var = tk.StringVar(value="")
        self.result_var = tk.StringVar(value="")

        self._build_ui()

    def _build_ui(self):
        style = ttk.Style(self)
        style.configure("TButton", padding=6)

        header = ttk.Frame(self, padding=10)
        header.pack(fill="x")

        display = ttk.Entry(header, textvariable=self.expr_var, font=("Helvetica", 18))
        display.pack(fill="x")

        result = ttk.Label(header, textvariable=self.result_var, font=("Helvetica", 14), foreground="#2b6")
        result.pack(fill="x", pady=(6, 0))

        toggle = ttk.Checkbutton(
            header,
            text="Degrees",
            variable=self.use_degrees,
            command=self._sync_preview,
        )
        toggle.pack(anchor="w", pady=(6, 0))

        keypad = ttk.Frame(self, padding=8)
        keypad.pack(fill="both", expand=True)

        buttons = [
            ["7", "8", "9", "/", "sqrt("],
            ["4", "5", "6", "*", "^"],
            ["1", "2", "3", "-", "("],
            ["0", ".", ")", "+", "%"],
            ["sin(", "cos(", "tan(", "log(", "ln("],
            ["asin(", "acos(", "atan(", "exp(", "abs("],
            ["pi", "e", "fact(", "//", "mod"],
            ["C", "DEL", "ANS", "=", "CLR"],
        ]

        for r, row in enumerate(buttons):
            for c, label in enumerate(row):
                action = lambda lbl=label: self.on_button(lbl)
                btn = ttk.Button(keypad, text=label, command=action)
                btn.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)

        for i in range(5):
            keypad.columnconfigure(i, weight=1)
        for i in range(len(buttons)):
            keypad.rowconfigure(i, weight=1)

        self.bind("<Return>", lambda _e: self.calculate())
        self.bind("<BackSpace>", lambda _e: self.backspace())
        self.bind("<Escape>", lambda _e: self.clear_all())
        self.expr_var.trace_add("write", lambda *_: self._sync_preview())

    def on_button(self, label):
        if label == "=":
            self.calculate()
            return
        if label == "C":
            self.clear_entry()
            return
        if label == "CLR":
            self.clear_all()
            return
        if label == "DEL":
            self.backspace()
            return
        if label == "ANS":
            ans = self.result_var.get()
            if ans:
                self.expr_var.set(self.expr_var.get() + ans)
            return
        if label == "mod":
            self.expr_var.set(self.expr_var.get() + "%")
            return
        self.expr_var.set(self.expr_var.get() + label)

    def calculate(self):
        expr = self.expr_var.get().strip()
        if not expr:
            return
        try:
            result = safe_eval(expr, use_degrees=self.use_degrees.get())
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            self.result_var.set(str(result))
        except Exception as exc:
            self.result_var.set(f"Error: {exc}")

    def _sync_preview(self):
        expr = self.expr_var.get().strip()
        if not expr:
            self.result_var.set("")
            return
        try:
            result = safe_eval(expr, use_degrees=self.use_degrees.get())
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            self.result_var.set(str(result))
        except Exception:
            self.result_var.set("")

    def backspace(self):
        value = self.expr_var.get()
        if value:
            self.expr_var.set(value[:-1])

    def clear_entry(self):
        self.expr_var.set("")

    def clear_all(self):
        self.expr_var.set("")
        self.result_var.set("")


if __name__ == "__main__":
    app = CalculatorApp()
    app.mainloop()
