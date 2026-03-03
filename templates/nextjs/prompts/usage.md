# Usage Guide - Next.js App Template

## Available UI Components

The following UI components are ALREADY AVAILABLE in this template.
IMPORT and USE them, do NOT recreate them:

### UI Primitives (src/components/ui/)

- **Accordion**: `import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion'`
- **Alert**: `import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'`
- **AlertDialog**: `import { AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader, AlertDialogFooter, AlertDialogTitle, AlertDialogDescription, AlertDialogAction, AlertDialogCancel } from '@/components/ui/alert-dialog'`
- **AspectRatio**: `import { AspectRatio } from '@/components/ui/aspect-ratio'`
- **Avatar**: `import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar'`
- **Badge**: `import { Badge, badgeVariants } from '@/components/ui/badge'`
- **Breadcrumb**: `import { Breadcrumb, BreadcrumbList, BreadcrumbItem, BreadcrumbLink, BreadcrumbPage, BreadcrumbSeparator, BreadcrumbEllipsis } from '@/components/ui/breadcrumb'`
- **Button**: `import { Button, buttonVariants } from '@/components/ui/button'`
- **Calendar**: `import { Calendar } from '@/components/ui/calendar'`
- **Card**: `import { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent } from '@/components/ui/card'`
- **Carousel**: `import { Carousel, CarouselContent, CarouselItem, CarouselNext, CarouselPrevious } from '@/components/ui/carousel'`
- **Checkbox**: `import { Checkbox } from '@/components/ui/checkbox'`
- **Collapsible**: `import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible'`
- **Command**: `import { Command, CommandDialog, CommandInput, CommandList, CommandEmpty, CommandGroup, CommandItem, CommandShortcut, CommandSeparator } from '@/components/ui/command'`
- **ContextMenu**: `import { ContextMenu, ContextMenuTrigger, ContextMenuContent, ContextMenuItem, ContextMenuCheckboxItem, ContextMenuRadioItem, ContextMenuLabel, ContextMenuSeparator, ContextMenuShortcut, ContextMenuGroup, ContextMenuPortal, ContextMenuSub, ContextMenuSubContent, ContextMenuSubTrigger, ContextMenuRadioGroup } from '@/components/ui/context-menu'`
- **Dialog**: `import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription, DialogClose, DialogOverlay, DialogPortal } from '@/components/ui/dialog'`
- **Drawer**: `import { Drawer, DrawerTrigger, DrawerContent, DrawerHeader, DrawerFooter, DrawerTitle, DialogDescription, DrawerClose, DrawerOverlay, DrawerPortal } from '@/components/ui/drawer'`
- **DropdownMenu**: `import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuCheckboxItem, DropdownMenuRadioItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuShortcut, DropdownMenuGroup, DropdownMenuPortal, DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger, DropdownMenuRadioGroup } from '@/components/ui/dropdown-menu'`
- **Form**: `import { useFormField, Form, FormItem, FormLabel, FormControl, FormDescription, FormMessage, FormField } from '@/components/ui/form'`
- **HoverCard**: `import { HoverCard, HoverCardTrigger, HoverCardContent } from '@/components/ui/hover-card'`
- **Input**: `import { Input } from '@/components/ui/input'`
- **InputOTP**: `import { InputOTP, InputOTPGroup, InputOTPSlot, InputOTPSeparator } from '@/components/ui/input-otp'`
- **Label**: `import { Label } from '@/components/ui/label'`
- **Menubar**: `import { Menubar, MenubarMenu, MenubarTrigger, MenubarContent, MenubarItem, MenubarSeparator, MenubarLabel, MenubarCheckboxItem, MenubarRadioGroup, MenubarRadioItem, MenubarPortal, MenubarSubContent, MenubarSubTrigger, MenubarGroup, MenubarSub, MenubarShortcut } from '@/components/ui/menubar'`
- **ModelSelector**: `import { ModelSelector } from '@/components/ui/model-selector'`
- **NavigationMenu**: `import { NavigationMenu, NavigationMenuList, NavigationMenuItem, NavigationMenuContent, NavigationMenuTrigger, NavigationMenuLink, NavigationMenuIndicator, NavigationMenuViewport, navigationMenuTriggerStyle } from '@/components/ui/navigation-menu'`
- **Pagination**: `import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from '@/components/ui/pagination'`
- **Popover**: `import { Popover, PopoverTrigger, PopoverContent, PopoverAnchor } from '@/components/ui/popover'`
- **Progress**: `import { Progress } from '@/components/ui/progress'`
- **RadioGroup**: `import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'`
- **Resizable**: `import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable'`
- **ScrollArea**: `import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area'`
- **Select**: `import { Select, SelectGroup, SelectValue, SelectTrigger, SelectContent, SelectLabel, SelectItem, SelectSeparator, SelectScrollUpButton, SelectScrollDownButton } from '@/components/ui/select'`
- **Separator**: `import { Separator } from '@/components/ui/separator'`
- **Sheet**: `import { Sheet, SheetTrigger, SheetContent, SheetHeader, SheetFooter, SheetTitle, SheetDescription, SheetClose, SheetOverlay, SheetPortal } from '@/components/ui/sheet'`
- **Sidebar**: `import { Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupAction, SidebarGroupContent, SidebarGroupLabel, SidebarHeader, SidebarInput, SidebarInset, SidebarMenu, SidebarMenuAction, SidebarMenuBadge, SidebarMenuButton, SidebarMenuItem, SidebarMenuSkeleton, SidebarMenuSub, SidebarMenuSubButton, SidebarMenuSubItem, SidebarProvider, SidebarRail, SidebarSeparator, SidebarTrigger, useSidebar } from '@/components/ui/sidebar'`
- **Skeleton**: `import { Skeleton } from '@/components/ui/skeleton'`
- **Slider**: `import { Slider } from '@/components/ui/slider'`
- **Sonner**: `import { Toaster } from '@/components/ui/sonner'` (toast notifications)
- **Switch**: `import { Switch } from '@/components/ui/switch'`
- **Table**: `import { Table, TableHeader, TableBody, TableFooter, TableHead, TableRow, TableCell, TableCaption } from '@/components/ui/table'`
- **Tabs**: `import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'`
- **Textarea**: `import { Textarea } from '@/components/ui/textarea'`
- **Toggle**: `import { Toggle, toggleVariants } from '@/components/ui/toggle'`
- **ToggleGroup**: `import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'`
- **Tooltip**: `import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '@/components/ui/tooltip'`

### Layout Guidelines

When creating layout.tsx or page files:
- IMPORT and USE the UI components listed above
- Example header: `<header><NavigationMenu>...</NavigationMenu></header>`
- Example footer: Use Footer component if available
- Do NOT create custom versions of existing components

### Import Examples

```tsx
// CORRECT: Import from @/components/ui/
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Form, FormField, FormItem, FormLabel, FormControl, FormMessage } from '@/components/ui/form';

// WRONG: Do NOT recreate these components
// Do NOT create a new Button component
// Do NOT create a new Card component
```

**CRITICAL RULE: Do NOT rewrite components that already exist in src/components/ui/. Import and reuse them.**

## Critical LLM Instructions

### Framework

- **Next.js 14 App Router only** - Do NOT use the Pages Router (`pages/` directory)
- **File-based routing** in `src/app/`
- **Server Components by default** - Add `"use client"` only when needed (useState, useEffect, event handlers, browser APIs)

### Styling

- **TailwindCSS v4** - CSS-based config via `@import "tailwindcss";` in globals.css
- **DO NOT modify**: `next.config.mjs`, `tsconfig.json`, `postcss.config.mjs`
- Use the **cn()** utility from `src/lib/cn.ts` for conditional classes

### File Structure

- **Layout**: Root layout in `src/app/layout.tsx`
- **Pages**: Create pages as `src/app/[route]/page.tsx` (e.g. `src/app/about/page.tsx` for `/about`)
- **API routes**: Create as `src/app/api/[route]/route.ts` (e.g. `src/app/api/users/route.ts` for `/api/users`)
- **Shared components**: Place in `src/components/`
- **Prebuilt UI kit**: Reuse components from `src/components/ui/*` first

### Data Fetching

- Use **async Server Components** for data fetching (no need for useEffect in Server Components)
- Or use **fetch** in Route Handlers (`route.ts`) for API responses
- For CMS/external data: call the backend API from Server Components using `fetch()`

### Conventions

- **TypeScript strict mode** - Use proper types, avoid `any`
- **Functional components with hooks** - Use standard React patterns
- **Metadata**: Export `metadata` or `generateMetadata` in layouts and pages for SEO
- **Prefer existing UI components** over creating duplicate primitives
- **Use named imports for UI components** (e.g. `import { Button } from '@/components/ui/button'`)

## Prebuilt UI Components

The template now includes a broad ShadCN-style UI kit in `src/components/ui/*` (accordion, alert-dialog, avatar, badge, breadcrumb, button, calendar, card, checkbox, command, dialog, drawer, dropdown-menu, form, input, input-otp, menubar, navigation-menu, pagination, popover, progress, radio-group, resizable, scroll-area, select, separator, sheet, sidebar, skeleton, slider, sonner, switch, table, tabs, textarea, toggle, tooltip, etc.).

Prefer reusing these components before creating custom primitives.

## Example Usage

```tsx
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function ExamplePanel() {
  return (
    <Card>
      <CardHeader>
        <Badge variant="secondary">Starter</Badge>
        <CardTitle>Control Panel</CardTitle>
      </CardHeader>
      <CardContent>
        <Button>Continue</Button>
      </CardContent>
    </Card>
  );
}
```
