import type { InputHTMLAttributes, TextareaHTMLAttributes } from "react";

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  id: string;
  label: string;
}

export function TextField({ id, label, ...props }: TextFieldProps) {
  return (
    <div>
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <input id={id} className="field" {...props} />
    </div>
  );
}

interface TextAreaFieldProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  id: string;
  label: string;
}

export function TextAreaField({ id, label, ...props }: TextAreaFieldProps) {
  return (
    <div>
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <textarea id={id} className="field" {...props} />
    </div>
  );
}
