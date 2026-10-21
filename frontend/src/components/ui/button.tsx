import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

// Adapted from shadcn/ui radix-nova; React 18 ref support and scoped tokens.
const buttonVariants = cva('home-button', {
  variants: {
    variant: {
      default: 'home-button-primary',
      outline: 'home-button-outline',
      ghost: 'home-button-ghost',
      destructive: 'home-button-destructive',
    },
    size: {
      default: 'home-button-default',
      sm: 'home-button-sm',
      icon: 'home-button-icon',
    },
  },
  defaultVariants: { variant: 'default', size: 'default' },
})

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, type, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        ref={ref}
        data-slot="button"
        type={asChild ? undefined : (type ?? 'button')}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    )
  },
)
Button.displayName = 'Button'

export { Button, buttonVariants }
