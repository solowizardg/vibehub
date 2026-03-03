# React-Vite Template Usage Guide

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
- **Drawer**: `import { Drawer, DrawerTrigger, DrawerContent, DrawerHeader, DrawerFooter, DrawerTitle, DrawerDescription, DrawerClose, DrawerOverlay, DrawerPortal } from '@/components/ui/drawer'`
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

## Tech Stack

- **React 19** - Latest React with concurrent features
- **Vite 6** - Fast bundler and dev server with HMR
- **TypeScript 5.7+** - Strict mode enabled
- **TailwindCSS v4** - CSS-based config, no tailwind.config.js; uses `@tailwindcss/vite` plugin

## File Structure Conventions

- `src/components/` - Reusable UI components
- `src/components/ui/` - Prebuilt UI kit (prefer reuse over creating duplicates)
- `src/pages/` - Page-level components (route targets)
- `src/lib/` - Utilities, helpers, API clients
- `src/hooks/` - Custom React hooks

## CSS Approach

- Use TailwindCSS v4 utility classes directly
- Use the `cn()` helper from `@/lib/cn` for conditional classes: `cn('base-classes', condition && 'conditional-classes', className)`
- Tailwind v4 scans source files automatically - no content config needed
- Theme customization goes in `src/index.css` via `@theme` blocks if needed

## Key Rules

1. **DO NOT modify** `vite.config.ts`, `tsconfig.json`, `tsconfig.app.json`, or `postcss.config.js`
2. The template includes a basic `App.tsx` shell - build pages and components from there
3. When adding new pages, update the routing in `App.tsx` (add `<Route>` entries)
4. Use `fetch()` to call backend APIs or CMS endpoints
5. Use **functional components with hooks** only - no class components
6. **Naming**: PascalCase for components, camelCase for utilities/hooks
7. **Always prefer existing UI components** under `src/components/ui/*` before creating new components
8. UI components use **named exports** (e.g. `import { Button } from '@/components/ui/button'`), not default exports

## Prebuilt UI Components

The template now includes a broad ShadCN-style UI kit in `src/components/ui/*` (accordion, alert-dialog, avatar, badge, breadcrumb, button, calendar, card, checkbox, command, dialog, drawer, dropdown-menu, form, input, input-otp, menubar, navigation-menu, pagination, popover, progress, radio-group, resizable, scroll-area, select, separator, sheet, sidebar, skeleton, slider, sonner, switch, table, tabs, textarea, toggle, tooltip, etc.).

Prefer reusing these components before creating custom primitives.

## Example Usage

```tsx
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function HeroCard() {
  return (
    <Card>
      <CardHeader>
        <Badge variant="secondary">New</Badge>
        <CardTitle>Dashboard</CardTitle>
      </CardHeader>
      <CardContent>
        <Button>Get Started</Button>
      </CardContent>
    </Card>
  );
}
```

## Adding a New Page

1. Create `src/pages/MyPage.tsx`
2. In `App.tsx`, add: `<Route path="/my-page" element={<MyPage />} />`

## Icons

Use `lucide-react` for icons: `import { ChevronRight } from 'lucide-react'`
