import type { Config, Menu, MenuItem, Variant } from './types'

const photo = (id: string) => `https://images.unsplash.com/${id}?auto=format&fit=crop&w=720&q=82`
const makeItem = (id: string, name: string, description: string, dietary_type: MenuItem['dietary_type'], image: string, price: number, minutes: number, variants?: Variant[]): MenuItem => ({
  id, name, description, dietary_type, image_url: photo(image), allergens: [],
  variants: variants || [{ id: `${id}-v`, name: 'Regular', offering_id: `${id}-o`, price_paise: price, version: 1, estimate_min_minutes: minutes - 5, estimate_max_minutes: minutes + 5, modifier_groups: [] }],
})

export const demoConfig: Config = {
  id: 'demo', display_name: 'Olive & Ember', name: 'Olive & Ember', address: 'A good meal, a little slower.', currency: 'INR',
  primary_color: '#263b32', accent_color: '#d97a55', logo_url: null, icon_url: null, hero_url: '/images/hero.jpg',
  ordering_enabled: true, delay_message: null, presentation: {},
}

export const demoMenu: Menu = {
  outlet_id: 'demo', menu_version: 1, ordering_enabled: true, delay_message: null,
  categories: [
    { id: 'signatures', name: 'Signatures', items: [
      makeItem('bowl', 'The Greenhouse Bowl', 'Roasted greens, avocado, herbed quinoa, crunchy seeds & lemon tahini.', 'VEGAN', 'photo-1512621776951-a57141f2eefd', 44900, 20),
      makeItem('pizza', 'Wild Mushroom Pizza', 'Creamy ricotta, forest mushrooms, mozzarella and truffle oil.', 'VEGETARIAN', 'photo-1574071318508-1cdbab80d002', 59500, 25),
      makeItem('chicken', 'Fire-Roasted Chicken', 'Slow-roasted chicken, whipped potatoes, charred greens & pan jus.', 'NON_VEGETARIAN', 'photo-1532550907401-a500c9a57435', 68500, 30),
    ] },
    { id: 'small', name: 'Small Plates', items: [
      makeItem('hummus', 'Silky Hummus & Pita', 'Warm pita, silky chickpea hummus, chilli oil and toasted sesame.', 'VEGAN', 'photo-1577906096429-f73c2c312435', 28500, 15),
      makeItem('salad', 'Heirloom Tomato Salad', 'Ripe tomatoes, basil, creamy burrata and aged balsamic.', 'VEGETARIAN', 'photo-1547592180-85f173990554', 34500, 15),
    ] },
    { id: 'sweet', name: 'Something Sweet', items: [
      makeItem('cake', 'Warm Chocolate Torte', 'Rich dark chocolate, vanilla bean cream and a pinch of sea salt.', 'VEGETARIAN', 'photo-1551024506-0bccd828d307', 29500, 15),
    ] },
    { id: 'drinks', name: 'Drinks', items: [
      makeItem('lemonade', 'Garden Lemonade', 'Fresh lemon, basil, a splash of soda and lots of ice.', 'VEGAN', 'photo-1546173159-315724a31696', 17500, 10),
    ] },
  ],
}
