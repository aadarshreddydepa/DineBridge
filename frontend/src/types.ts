export type DietaryType = 'UNSPECIFIED' | 'VEGETARIAN' | 'VEGAN' | 'NON_VEGETARIAN'

export interface ModifierOption {
  id: string
  name: string
  price_delta_paise: number
  version: number
}
export interface ModifierGroup {
  id: string
  name: string
  min_choices: number
  max_choices: number
  options: ModifierOption[]
}
export interface Variant {
  id: string
  name: string
  offering_id: string
  price_paise: number
  version: number
  estimate_min_minutes: number
  estimate_max_minutes: number
  modifier_groups: ModifierGroup[]
}
export interface MenuItem {
  id: string
  name: string
  description: string
  dietary_type: DietaryType
  allergens: string[]
  image_url: string | null
  image_urls?: string[]
  variants: Variant[]
}
export interface Category {
  id: string
  name: string
  items: MenuItem[]
}
export interface Menu {
  outlet_id: string
  menu_version: number
  ordering_enabled: boolean
  delay_message: string | null
  categories: Category[]
}
export interface Config {
  id: string
  display_name: string
  name: string
  address: string | null
  currency: string
  primary_color: string
  accent_color: string
  logo_url: string | null
  icon_url: string | null
  hero_url: string | null
  ordering_enabled: boolean
  delay_message: string | null
  presentation: Record<string, unknown>
}
export interface CartLine {
  key: string
  itemId: string
  itemName: string
  itemImage: string | null
  variantName: string
  offeringId: string
  expectedVersion: number
  basePrice: number
  unitPrice: number
  optionIds: string[]
  optionNames: string[]
  notes: string
  quantity: number
}
export interface OrderLine {
  id: string
  item_name: string
  variant_name: string
  quantity: number
  base_unit_paise: number
  modifier_unit_paise: number
  queued_qty: number
  preparing_qty: number
  ready_qty: number
  served_qty: number
  cancelled_qty: number
}
export interface Order {
  id: string
  display_ref: string
  placed_at?: string
  seen_at?: string | null
  subtotal_paise: number
  lines: OrderLine[]
}
