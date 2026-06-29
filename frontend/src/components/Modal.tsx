import type { ReactNode } from "react";

interface ModalProps {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "lg" | "xl";
}

export default function Modal({ title, open, onClose, children, footer, size }: ModalProps) {
  if (!open) return null;
  return (
    <>
      <div className="modal d-block" tabIndex={-1} role="dialog">
        <div className={`modal-dialog modal-dialog-centered ${size ? `modal-${size}` : ""}`}>
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">{title}</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <div className="modal-body">{children}</div>
            {footer && <div className="modal-footer">{footer}</div>}
          </div>
        </div>
      </div>
      <div className="modal-backdrop show" onClick={onClose} />
    </>
  );
}
