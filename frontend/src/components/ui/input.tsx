import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

// Adapted from shadcn/ui radix-nova, with React 18 forwarded refs.
const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    data-slot="input"
    className={cn('home-input', className)}
    {...props}
  />
))
Input.displayName = 'Input'

export { Input }
