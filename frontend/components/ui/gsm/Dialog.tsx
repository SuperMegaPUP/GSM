'use client';

/**
 * GSM Design System — Dialog
 *
 * Modal with spring-in animation. Backdrop blur. ESC to close.
 * Replaces @base-ui/react/dialog with motion-enhanced version.
 *
 * Usage:
 *   const [open, setOpen] = useState(false);
 *   <Dialog open={open} onOpenChange={setOpen}>
 *     <DialogTrigger asChild>
 *       <button className="btn btn-primary">Открыть</button>
 *     </DialogTrigger>
 *     <DialogContent>
 *       <DialogHeader>
 *         <DialogTitle>Заголовок</DialogTitle>
 *         <DialogDescription>Описание</DialogDescription>
 *       </DialogHeader>
 *       <p>Тело диалога</p>
 *       <DialogFooter>
 *         <button className="btn btn-ghost" onClick={() => setOpen(false)}>Отмена</button>
 *         <button className="btn btn-primary">OK</button>
 *       </DialogFooter>
 *     </DialogContent>
 *   </Dialog>
 */

import { AnimatePresence, motion } from 'framer-motion';
import {
  createContext,
  useContext,
  useEffect,
  type ReactNode,
} from 'react';

interface DialogContextValue {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DialogContext = createContext<DialogContextValue | null>(null);

function useDialog() {
  const ctx = useContext(DialogContext);
  if (!ctx) throw new Error('Dialog components must be inside <Dialog>');
  return ctx;
}

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
}

export function Dialog({ open, onOpenChange, children }: DialogProps) {
  // ESC to close + lock body scroll
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onOpenChange(false);
    };
    document.addEventListener('keydown', handler);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handler);
      document.body.style.overflow = '';
    };
  }, [open, onOpenChange]);

  return (
    <DialogContext.Provider value={{ open, onOpenChange }}>
      <AnimatePresence>
        {open && children}
      </AnimatePresence>
    </DialogContext.Provider>
  );
}

interface DialogContentProps {
  children: ReactNode;
  className?: string;
}

export function DialogContent({ children, className = '' }: DialogContentProps) {
  const { onOpenChange } = useDialog();

  return (
    <motion.div
      className="fixed inset-0 z-[var(--z-modal)] grid place-items-center p-4"
      style={{
        background: 'oklch(0.10 0.005 250 / 0.5)',
        backdropFilter: 'blur(8px)',
      }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      onClick={(e) => e.target === e.currentTarget && onOpenChange(false)}
    >
      <motion.div
        role="dialog"
        aria-modal="true"
        className={`w-full max-w-lg rounded-xl border bg-[var(--surface-1)] p-7 shadow-2xl ${className}`}
        initial={{ scale: 0.95, y: 8, opacity: 0 }}
        animate={{ scale: 1, y: 0, opacity: 1 }}
        exit={{ scale: 0.98, y: 4, opacity: 0 }}
        transition={{ duration: 0.24, ease: [0.34, 1.56, 0.64, 1] }}
      >
        {children}
      </motion.div>
    </motion.div>
  );
}

export function DialogTrigger({
  children,
}: {
  children: ReactNode;
}) {
  const { onOpenChange } = useDialog();
  return (
    <span onClick={() => onOpenChange(true)} style={{ display: 'contents' }}>
      {children}
    </span>
  );
}

export function DialogHeader({ children }: { children: ReactNode }) {
  return <div className="mb-4">{children}</div>;
}

export function DialogTitle({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <h3 className={`mb-1 text-xl font-semibold tracking-tight ${className}`}>{children}</h3>
  );
}

export function DialogDescription({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <p className={`text-sm text-[var(--sidebar-muted)] ${className}`}>{children}</p>
  );
}

export function DialogFooter({ children }: { children: ReactNode }) {
  return (
    <div className="mt-6 flex justify-end gap-2">{children}</div>
  );
}
