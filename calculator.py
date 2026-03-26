#!/usr/bin/env python3
import math
import tkinter as tk


class CalculatorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Calculator")
        self.root.resizable(False, False)

        self.expr = ""
        self.memory_value = 0.0

        self.display_var = tk.StringVar(value="0")
        self.display = tk.Entry(
            root,
            textvariable=self.display_var,
            font=("Helvetica", 24),
            justify="right",
            bd=10,
            relief="sunken",
            state="readonly",
            width=16,
        )
        self.display.grid(row=0, column=0, columnspan=4, padx=10, pady=10)

        self._build_buttons()

    def _build_buttons(self) -> None:
        btn = self._btn

        btn("MC", 1, 0, self.clear_memory)
        btn("MR", 1, 1, self.recall_memory)
        btn("M+", 1, 2, self.add_memory)
        btn("M-", 1, 3, self.sub_memory)

        btn("C", 2, 0, self.clear_all)
        btn("⌫", 2, 1, self.backspace)
        btn("%", 2, 2, lambda: self.append("%"))
        btn("÷", 2, 3, lambda: self.append("/"))

        btn("7", 3, 0, lambda: self.append("7"))
        btn("8", 3, 1, lambda: self.append("8"))
        btn("9", 3, 2, lambda: self.append("9"))
        btn("×", 3, 3, lambda: self.append("*"))

        btn("4", 4, 0, lambda: self.append("4"))
        btn("5", 4, 1, lambda: self.append("5"))
        btn("6", 4, 2, lambda: self.append("6"))
        btn("-", 4, 3, lambda: self.append("-"))

        btn("1", 5, 0, lambda: self.append("1"))
        btn("2", 5, 1, lambda: self.append("2"))
        btn("3", 5, 2, lambda: self.append("3"))
        btn("+", 5, 3, lambda: self.append("+"))

        btn("0", 6, 0, lambda: self.append("0"))
        btn(".", 6, 1, lambda: self.append("."))
        btn("(", 6, 2, lambda: self.append("("))
        btn(")", 6, 3, lambda: self.append(")"))

        btn("√", 7, 0, self.sqrt_value)
        btn("x²", 7, 1, self.square_value)
        btn("^", 7, 2, lambda: self.append("**"))
        btn("=", 7, 3, self.calculate, primary=True)

    def _btn(self, text: str, row: int, col: int, cmd, primary: bool = False) -> None:
        bg = "#e6e6e6" if not primary else "#ffcc66"
        btn = tk.Button(
            self.root,
            text=text,
            width=5,
            height=2,
            font=("Helvetica", 16),
            bg=bg,
            command=cmd,
        )
        btn.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

    def _set_display(self, value: str) -> None:
        self.display_var.set(value)

    def append(self, value: str) -> None:
        if self.expr == "0":
            self.expr = ""
        self.expr += value
        self._set_display(self.expr)

    def clear_all(self) -> None:
        self.expr = ""
        self._set_display("0")

    def backspace(self) -> None:
        self.expr = self.expr[:-1]
        self._set_display(self.expr if self.expr else "0")

    def sqrt_value(self) -> None:
        try:
            result = math.sqrt(self._eval_expr())
            self.expr = self._format_result(result)
            self._set_display(self.expr)
        except Exception:
            self._set_display("Error")
            self.expr = ""

    def square_value(self) -> None:
        try:
            result = self._eval_expr() ** 2
            self.expr = self._format_result(result)
            self._set_display(self.expr)
        except Exception:
            self._set_display("Error")
            self.expr = ""

    def calculate(self) -> None:
        try:
            result = self._eval_expr()
            self.expr = self._format_result(result)
            self._set_display(self.expr)
        except Exception:
            self._set_display("Error")
            self.expr = ""

    def _eval_expr(self) -> float:
        if not self.expr:
            return 0.0
        safe = self.expr.replace("×", "*").replace("÷", "/")
        return float(eval(safe, {"__builtins__": {}}, {}))

    def _format_result(self, value: float) -> str:
        if value.is_integer():
            return str(int(value))
        return str(value)

    def clear_memory(self) -> None:
        self.memory_value = 0.0

    def recall_memory(self) -> None:
        self.expr = self._format_result(self.memory_value)
        self._set_display(self.expr)

    def add_memory(self) -> None:
        try:
            self.memory_value += self._eval_expr()
        except Exception:
            self._set_display("Error")
            self.expr = ""

    def sub_memory(self) -> None:
        try:
            self.memory_value -= self._eval_expr()
        except Exception:
            self._set_display("Error")
            self.expr = ""


def main() -> None:
    root = tk.Tk()
    CalculatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
