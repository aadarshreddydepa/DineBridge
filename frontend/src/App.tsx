import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { ArrowLeft, ArrowRight, Check, Clock3, Coffee, Flame, Heart, Leaf, MapPin, Menu as MenuIcon, Minus, Plus, Search, ShoppingBag, Sparkles, UtensilsCrossed, X } from 'lucide-react'
import { api, ApiError } from './api'
import { demoConfig, demoMenu } from './demo'
import type { CartLine, Config, Menu, MenuItem, ModifierGroup, Order, Variant } from './types'

const params = new URLSearchParams(window.location.search)
const outletId = params.get('outlet') || ''
const demo = window.location.pathname === '/demo' || params.get('demo') === '1'
const storageKey = `dinebridge:cart:${demo ? 'demo' : outletId}`

function readCart(): CartLine[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(storageKey) || '[]')
    return Array.isArray(parsed) ? parsed as CartLine[] : []
  } catch { return [] }
}

function formatMoney(paise: number, currency: string) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 0 }).format(paise / 100)
}

function dietaryLabel(type: MenuItem['dietary_type']) {
  if (type === 'VEGAN') return 'Vegan'
  if (type === 'VEGETARIAN') return 'Vegetarian'
  if (type === 'NON_VEGETARIAN') return 'Non-veg'
  return ''
}

function itemPrice(item: MenuItem) {
  return Math.min(...item.variants.map(variant => variant.price_paise))
}

function optionGroupValid(group: ModifierGroup, selected: string[]) {
  const count = group.options.filter(option => selected.includes(option.id)).length
  return count >= group.min_choices && count <= group.max_choices
}

function Intro({ name, onClose }: { name: string; onClose: () => void }) {
  return <div className="intro" role="dialog" aria-label={`Welcome to ${name}`}>
    <div className="intro-glow" />
    <div className="intro-content">
      <div className="intro-mark"><UtensilsCrossed size={36} strokeWidth={1.5} /></div>
      <span className="eyebrow light intro-step one">YOUR TABLE IS READY</span>
      <h1 className="intro-step two">Welcome to<br /><em>{name}</em></h1>
      <p className="intro-step three">Good food is just a tap away.</p>
      <button className="intro-button intro-step four" onClick={onClose}>Explore the menu <ArrowRight size={17} /></button>
    </div>
    <span className="intro-bottom">FRESHLY MADE • HAPPILY SHARED</span>
  </div>
}

function FoodImage({ item, className = '' }: { item: MenuItem; className?: string }) {
  const [failed, setFailed] = useState(false)
  return item.image_url && !failed
    ? <img className={className} src={item.image_url} alt={item.name} loading="lazy" onError={() => setFailed(true)} />
    : <div className={`image-fallback ${className}`} aria-label={item.name}><UtensilsCrossed size={33} strokeWidth={1.2} /></div>
}

function ItemSheet({ item, currency, onClose, onAdd }: { item: MenuItem; currency: string; onClose: () => void; onAdd: (item: MenuItem, variant: Variant, options: string[], notes: string, quantity: number) => void }) {
  const [variant, setVariant] = useState(item.variants[0])
  const [options, setOptions] = useState<string[]>([])
  const [notes, setNotes] = useState('')
  const [quantity, setQuantity] = useState(1)
  const valid = variant.modifier_groups.every(group => optionGroupValid(group, options))
  const optionCost = variant.modifier_groups.flatMap(group => group.options).filter(option => options.includes(option.id)).reduce((sum, option) => sum + option.price_delta_paise, 0)

  function toggleOption(group: ModifierGroup, id: string) {
    if (options.includes(id)) { setOptions(options.filter(option => option !== id)); return }
    const groupIds = group.options.map(option => option.id)
    const selectedGroup = options.filter(option => groupIds.includes(option))
    if (group.max_choices === 1) setOptions([...options.filter(option => !groupIds.includes(option)), id])
    else if (selectedGroup.length < group.max_choices) setOptions([...options, id])
  }

  return <div className="sheet-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}>
    <section className="sheet item-sheet" role="dialog" aria-modal="true" aria-label={item.name}>
      <div className="sheet-handle" />
      <button className="sheet-close" onClick={onClose} aria-label="Close item"><X size={20} /></button>
      <div className="detail-image-wrap"><FoodImage item={item} className="detail-image" /></div>
      <div className="sheet-body">
        <div className="detail-topline"><span className="eyebrow">MADE FOR YOU</span><span className="dietary-detail"><span className={`diet-dot ${item.dietary_type.toLowerCase()}`} />{dietaryLabel(item.dietary_type)}</span></div>
        <h2>{item.name}</h2>
        <p className="detail-description">{item.description}</p>
        {!!item.allergens.length && <p className="allergen-note">Contains: {item.allergens.join(', ')}</p>}
        {item.variants.length > 1 && <div className="choice-section"><div className="choice-heading"><h3>Choose your size</h3><span>Pick one</span></div><div className="variant-list">{item.variants.map(option => <button key={option.id} className={`variant-choice ${variant.id === option.id ? 'selected' : ''}`} onClick={() => { setVariant(option); setOptions([]) }}><span>{option.name}</span><span>{formatMoney(option.price_paise, currency)} {variant.id === option.id && <Check size={17} />}</span></button>)}</div></div>}
        {variant.modifier_groups.map(group => <div className="choice-section" key={group.id}><div className="choice-heading"><h3>{group.name}</h3><span>{group.min_choices ? `Choose ${group.min_choices}${group.max_choices > group.min_choices ? `–${group.max_choices}` : ''}` : 'Optional'}</span></div><div className="variant-list">{group.options.map(option => <button key={option.id} className={`variant-choice ${options.includes(option.id) ? 'selected' : ''}`} onClick={() => toggleOption(group, option.id)}><span>{option.name}</span><span>{option.price_delta_paise ? `+${formatMoney(option.price_delta_paise, currency)}` : 'Included'} {options.includes(option.id) && <Check size={17} />}</span></button>)}</div></div>)}
        <label className="notes-label" htmlFor="item-notes">Any special requests?</label>
        <textarea id="item-notes" maxLength={300} placeholder="Let us know how you like it..." value={notes} onChange={event => setNotes(event.target.value)} />
      </div>
      <div className="sheet-action"><div className="quantity"><button onClick={() => setQuantity(Math.max(1, quantity - 1))} aria-label="Decrease quantity"><Minus size={18} /></button><span>{quantity}</span><button onClick={() => setQuantity(Math.min(20, quantity + 1))} aria-label="Increase quantity"><Plus size={18} /></button></div><button className="primary-button flex-button" disabled={!valid} onClick={() => { onAdd(item, variant, options, notes.trim(), quantity); onClose() }}>Add to order <span>{formatMoney((variant.price_paise + optionCost) * quantity, currency)}</span></button></div>
    </section>
  </div>
}

function CartSheet({ cart, currency, orderingEnabled, onClose, onQuantity, onSubmit, busy, error, hasAccess, demoMode }: { cart: CartLine[]; currency: string; orderingEnabled: boolean; onClose: () => void; onQuantity: (key: string, change: number) => void; onSubmit: () => void; busy: boolean; error: string; hasAccess: boolean; demoMode: boolean }) {
  const subtotal = cart.reduce((sum, line) => sum + line.unitPrice * line.quantity, 0)
  return <div className="sheet-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}>
    <section className="sheet cart-sheet" role="dialog" aria-modal="true" aria-label="Your order">
      <div className="sheet-handle" />
      <div className="cart-header"><div><span className="eyebrow">ALMOST THERE</span><h2>Your order</h2></div><button className="icon-button" onClick={onClose} aria-label="Close cart"><X size={21} /></button></div>
      <div className="cart-body">{cart.length ? cart.map(line => <div className="cart-line" key={line.key}><div className="cart-line-image">{line.itemImage ? <img src={line.itemImage} alt="" /> : <UtensilsCrossed size={24} />}</div><div className="cart-line-main"><h3>{line.itemName}</h3><p>{line.variantName}{line.optionNames.length ? ` · ${line.optionNames.join(', ')}` : ''}</p>{line.notes && <small>“{line.notes}”</small>}<div className="cart-line-bottom"><strong>{formatMoney(line.unitPrice * line.quantity, currency)}</strong><div className="quantity small"><button onClick={() => onQuantity(line.key, -1)} aria-label={`Remove one ${line.itemName}`}><Minus size={15} /></button><span>{line.quantity}</span><button onClick={() => onQuantity(line.key, 1)} aria-label={`Add one ${line.itemName}`}><Plus size={15} /></button></div></div></div></div>) : <div className="empty-cart"><ShoppingBag size={38} strokeWidth={1.3} /><h3>Nothing in your basket yet</h3><p>Let's find something delicious.</p><button className="secondary-button" onClick={onClose}>Browse the menu</button></div>}</div>
      {!!cart.length && <div className="cart-footer"><div className="bill-row"><span>Subtotal</span><strong>{formatMoney(subtotal, currency)}</strong></div><p className="bill-note">Taxes and any service charges are handled by the restaurant at billing.</p>{error && <p className="inline-error" role="alert">{error}</p>}{!hasAccess && !demoMode && <p className="inline-error">Scan your table's QR code to place this order.</p>}{demoMode && <p className="demo-note">Preview mode · orders are disabled.</p>}<button className="primary-button checkout-button" disabled={!orderingEnabled || !hasAccess || demoMode || busy} onClick={onSubmit}>{busy ? 'Placing your order…' : !orderingEnabled ? 'Ordering paused' : 'Place order'} <ArrowRight size={18} /></button></div>}
    </section>
  </div>
}

export default function App() {
  const [config, setConfig] = useState<Config | null>(demo ? demoConfig : null)
  const [menu, setMenu] = useState<Menu | null>(demo ? demoMenu : null)
  const [loading, setLoading] = useState(!demo && !!outletId)
  const [loadError, setLoadError] = useState('')
  const [tableLabel, setTableLabel] = useState(demo ? 'Table 08' : '')
  const [hasAccess, setHasAccess] = useState(demo)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('all')
  const [diet, setDiet] = useState<'veg' | 'nonveg'>('veg')
  const [selectedItem, setSelectedItem] = useState<MenuItem | null>(null)
  const [cartOpen, setCartOpen] = useState(false)
  const [cart, setCart] = useState<CartLine[]>(readCart)
  const [activeTab, setActiveTab] = useState<'menu' | 'orders'>('menu')
  const [orders, setOrders] = useState<Order[]>([])
  const [orderLoading, setOrderLoading] = useState(false)
  const [orderError, setOrderError] = useState('')
  const [submitBusy, setSubmitBusy] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [serviceMessage, setServiceMessage] = useState('')
  const [introOpen, setIntroOpen] = useState(() => params.get('intro') === '1' || !sessionStorage.getItem(`dinebridge:intro:${demo ? 'demo' : outletId}`))

  useEffect(() => {
    if (demo || !outletId) return
    let live = true
    Promise.all([api.config(outletId), api.menu(outletId)]).then(([cfg, catalog]) => {
      if (!live) return
      setConfig(cfg); setMenu(catalog); setLoading(false)
      document.title = `${cfg.display_name} · Menu`
    }).catch((error: Error) => { if (live) { setLoadError(error.message); setLoading(false) } })
    api.access().then(access => { if (live && access.outlet_id === outletId) { setHasAccess(true); setTableLabel(access.table_label) } }).catch(() => {})
    return () => { live = false }
  }, [])

  useEffect(() => {
    if (!introOpen || !config) return
    const timer = window.setTimeout(() => closeIntro(), 2400)
    return () => window.clearTimeout(timer)
  }, [introOpen, config])

  useEffect(() => { localStorage.setItem(storageKey, JSON.stringify(cart)) }, [cart])
  useEffect(() => {
    if (!cartOpen && !selectedItem) return
    const oldOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { setCartOpen(false); setSelectedItem(null) } }
    window.addEventListener('keydown', escape)
    return () => { document.body.style.overflow = oldOverflow; window.removeEventListener('keydown', escape) }
  }, [cartOpen, selectedItem])

  useEffect(() => {
    if (activeTab !== 'orders' || demo || !hasAccess) return
    refreshOrders()
    const timer = window.setInterval(refreshOrders, 15000)
    return () => window.clearInterval(timer)
  }, [activeTab, hasAccess])

  function closeIntro() { setIntroOpen(false); sessionStorage.setItem(`dinebridge:intro:${demo ? 'demo' : outletId}`, '1') }
  async function refreshOrders() {
    setOrderLoading(true)
    try { const result = await api.orders(); setOrders(result.orders); setOrderError('') }
    catch (error) { setOrderError((error as Error).message) }
    finally { setOrderLoading(false) }
  }
  function addItem(item: MenuItem, variant: Variant, optionIds: string[], notes: string, quantity: number) {
    const sorted = [...optionIds].sort()
    const key = JSON.stringify([variant.offering_id, sorted, notes])
    const selectedOptions = variant.modifier_groups.flatMap(group => group.options).filter(option => sorted.includes(option.id))
    const unitPrice = variant.price_paise + selectedOptions.reduce((sum, option) => sum + option.price_delta_paise, 0)
    setCart(current => {
      const existing = current.find(line => line.key === key)
      if (existing) return current.map(line => line.key === key ? { ...line, quantity: Math.min(20, line.quantity + quantity) } : line)
      if (current.length >= 20) { setSubmitError('Your order can contain up to 20 different items.'); return current }
      return [...current, { key, itemId: item.id, itemName: item.name, itemImage: item.image_url, variantName: variant.name, offeringId: variant.offering_id, expectedVersion: variant.version, basePrice: variant.price_paise, unitPrice, optionIds: sorted, optionNames: selectedOptions.map(option => option.name), notes, quantity }]
    })
    setSubmitError('')
  }
  function changeQuantity(key: string, change: number) {
    setCart(current => current.map(line => line.key === key ? { ...line, quantity: Math.min(20, line.quantity + change) } : line).filter(line => line.quantity > 0))
    setSubmitError('')
  }
  async function submitOrder() {
    if (!cart.length || demo) return
    setSubmitBusy(true); setSubmitError('')
    const payload = { lines: cart.map(line => ({ offering_id: line.offeringId, quantity: line.quantity, expected_version: line.expectedVersion, expected_price_paise: line.basePrice, option_ids: line.optionIds, notes: line.notes })) }
    const signature = JSON.stringify(payload)
    const pendingKey = `dinebridge:pending:${outletId}`
    let pending: { signature: string; id: string } | null = null
    try { pending = JSON.parse(localStorage.getItem(pendingKey) || 'null') } catch { /* ignore stale state */ }
    const id = pending?.signature === signature ? pending.id : crypto.randomUUID()
    localStorage.setItem(pendingKey, JSON.stringify({ signature, id }))
    try {
      const order = await api.post<Order>('/api/v1/orders', payload, id)
      localStorage.removeItem(pendingKey)
      setCart([]); setCartOpen(false); setOrders(current => [order, ...current.filter(old => old.id !== order.id)]); setActiveTab('orders')
    } catch (error) {
      const failure = error as ApiError
      if (failure.status && failure.status < 500) localStorage.removeItem(pendingKey)
      if (failure.code === 'PRICE_CHANGED') {
        setSubmitError('A price changed. Review the updated basket total before ordering again.')
        api.menu(outletId).then(latest => {
          setMenu(latest)
          const offerings = latest.categories.flatMap(group => group.items.flatMap(item => item.variants))
          setCart(current => current.map(line => {
            const variant = offerings.find(option => option.offering_id === line.offeringId)
            if (!variant) return line
            const modifierPrice = variant.modifier_groups.flatMap(group => group.options).filter(option => line.optionIds.includes(option.id)).reduce((sum, option) => sum + option.price_delta_paise, 0)
            return { ...line, expectedVersion: variant.version, basePrice: variant.price_paise, unitPrice: variant.price_paise + modifierPrice }
          }))
        }).catch(() => setSubmitError('The price changed, but the refreshed menu could not load. Please try again.'))
      } else if (failure.code === 'ITEM_UNAVAILABLE') {
        setSubmitError('An item is no longer available. Please remove it from your basket.')
        api.menu(outletId).then(setMenu).catch(() => {})
      } else setSubmitError(failure.message)
    } finally { setSubmitBusy(false) }
  }
  async function requestService(kind: 'WAITER' | 'BILL') {
    setServiceMessage('Sending request…')
    try { await api.post('/api/v1/service-requests', { kind }); setServiceMessage(kind === 'WAITER' ? 'A team member is on their way.' : 'We have let the team know you are ready for the bill.') }
    catch (error) { setServiceMessage((error as Error).message) }
  }

  const filtered = useMemo(() => (menu?.categories || []).map(group => ({ ...group, items: group.items.filter(item => (category === 'all' || category === group.id) && (diet === 'veg' ? item.dietary_type === 'VEGETARIAN' || item.dietary_type === 'VEGAN' : item.dietary_type === 'NON_VEGETARIAN') && `${item.name} ${item.description}`.toLowerCase().includes(search.toLowerCase().trim())) })).filter(group => group.items.length), [menu, category, diet, search])
  const cartCount = cart.reduce((sum, line) => sum + line.quantity, 0)
  const subtotal = cart.reduce((sum, line) => sum + line.unitPrice * line.quantity, 0)
  const theme = { '--brand': config?.primary_color || '#263b32', '--accent': config?.accent_color || '#d97a55' } as CSSProperties
  const currency = config?.currency || 'INR'
  const brandTagline = typeof config?.presentation?.tagline === 'string' ? config.presentation.tagline : 'EAT WELL. FEEL GOOD.'
  const heroKicker = typeof config?.presentation?.hero_kicker === 'string' ? config.presentation.hero_kicker : 'THE GOOD FOOD CLUB'
  const heroHeadline = typeof config?.presentation?.hero_headline === 'string' ? config.presentation.hero_headline : 'Stay a while.'
  const heroEmphasis = typeof config?.presentation?.hero_emphasis === 'string' ? config.presentation.hero_emphasis : 'Eat beautifully.'
  const heroCaption = typeof config?.presentation?.hero_caption === 'string' ? config.presentation.hero_caption : 'Fresh ingredients, thoughtful plates, and something lovely for every appetite.'

  if (!demo && !outletId) return <div className="setup-screen"><div className="setup-card"><div className="setup-icon"><UtensilsCrossed size={30} /></div><span className="eyebrow">WELCOME TO DINEBRIDGE</span><h1>Your table awaits.</h1><p>Scan the QR code on your table to open the restaurant's menu.</p><a className="primary-button" href="/demo">Preview the customer experience <ArrowRight size={18} /></a></div></div>
  if (loading) return <div className="loading-screen"><div className="loading-logo"><UtensilsCrossed size={27} /></div><p>Preparing your menu…</p><div className="loading-line" /></div>
  if (loadError || !config || !menu) return <div className="setup-screen"><div className="setup-card"><span className="eyebrow">COULD NOT LOAD MENU</span><h1>Let's try that again.</h1><p>{loadError || 'This menu is unavailable right now.'}</p><button className="primary-button" onClick={() => window.location.reload()}>Retry <ArrowRight size={18} /></button></div></div>

  return <div className="app" style={theme}>
    {introOpen && <Intro name={config.display_name} onClose={closeIntro} />}
    <header className="site-header"><div className="header-inner"><div className="brand-lockup">{config.logo_url ? <img src={config.logo_url} alt={config.display_name} className="brand-logo" /> : <div className="brand-symbol"><UtensilsCrossed size={19} strokeWidth={1.7} /></div>}<div><span className="brand-name">{config.display_name}</span><span className="brand-subtitle">{brandTagline}</span></div></div><div className="header-actions">{tableLabel && <span className="table-pill"><MapPin size={14} />{tableLabel}</span>}<button className="header-cart" onClick={() => setCartOpen(true)} aria-label={`Open basket with ${cartCount} items`}><ShoppingBag size={20} strokeWidth={1.8} />{cartCount > 0 && <span className="cart-badge">{cartCount}</span>}</button></div></div></header>

    <main className="main-shell">
      {activeTab === 'menu' ? <>
        <div className="welcome-line"><span>GOOD {new Date().getHours() < 12 ? 'MORNING' : new Date().getHours() < 17 ? 'AFTERNOON' : 'EVENING'} <span className="sun-dot">✳</span></span><span>Handmade with heart, served for you.</span></div>
        <section className="hero" style={{ backgroundImage: `linear-gradient(90deg, rgba(25,42,32,.84) 0%, rgba(25,42,32,.52) 45%, rgba(25,42,32,.08) 100%), url("${config.hero_url || '/images/hero.jpg'}")` }}><div className="hero-copy"><span className="hero-kicker"><span className="kicker-line" /> {heroKicker}</span><h1>{heroHeadline}<br /><em>{heroEmphasis}</em></h1><p>{heroCaption}</p><button onClick={() => document.getElementById('menu-section')?.scrollIntoView({ behavior: 'smooth' })}>Explore the menu <ArrowRight size={16} /></button></div><div className="hero-stamp"><Sparkles size={17} /> FRESH<br />DAILY</div></section>
        <div className="feature-strip"><div><span className="feature-icon"><Leaf size={18} /></span><span><strong>Fresh by nature</strong><small>Made with care, every day</small></span></div><div><span className="feature-icon"><Clock3 size={18} /></span><span><strong>Order at your pace</strong><small>Settle in and take your time</small></span></div><div><span className="feature-icon"><Heart size={18} /></span><span><strong>A little something for all</strong><small>Choices for every appetite</small></span></div></div>
        <section id="menu-section" className="menu-section"><div className="section-heading"><div><span className="eyebrow">THE MENU</span><h2>What sounds good?</h2></div><span className="section-squiggle">✦</span></div>{(!menu.ordering_enabled || config.delay_message) && <div className="notice"><Clock3 size={18} /><span>{config.delay_message || menu.delay_message || 'Ordering is paused for now. You can still explore the menu.'}</span></div>}
          <div className="menu-controls"><label className="search-box"><Search size={20} /><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search menu" aria-label="Search the menu" />{search && <button onClick={() => setSearch('')} aria-label="Clear search"><X size={16} /></button>}</label><div className="diet-control"><span className={`diet-label ${diet === 'veg' ? 'active veg' : ''}`}>Veg</span><button className={`diet-switch ${diet === 'nonveg' ? 'nonveg' : ''}`} role="switch" aria-checked={diet === 'nonveg'} aria-label="Show non-vegetarian dishes" onClick={() => setDiet(diet === 'veg' ? 'nonveg' : 'veg')}><span className="switch-track-icon left"><Leaf size={16} strokeWidth={2} /></span><span className="switch-track-icon right"><Flame size={16} strokeWidth={2} /></span><span className="diet-switch-knob"><Leaf className="knob-icon veg" size={20} strokeWidth={2.3} /><Flame className="knob-icon nonveg" size={20} strokeWidth={2.3} /></span></button><span className={`diet-label ${diet === 'nonveg' ? 'active nonveg' : ''}`}>Non-veg</span></div></div>
          <div className="categories" role="tablist" aria-label="Menu categories"><button className={category === 'all' ? 'active' : ''} role="tab" aria-selected={category === 'all'} onClick={() => setCategory('all')}>All dishes</button>{menu.categories.map(group => <button key={group.id} role="tab" aria-selected={category === group.id} className={category === group.id ? 'active' : ''} onClick={() => setCategory(group.id)}>{group.name}</button>)}</div>
          {filtered.length ? filtered.map(group => <section className="category-block" key={group.id}><div className="category-heading"><div><span className="category-accent" /><h3>{group.name}</h3></div><span>{group.items.length} {group.items.length === 1 ? 'dish' : 'dishes'}</span></div><div className="dish-grid">{group.items.map((item, index) => <article className="dish-card" key={item.id} style={{ animationDelay: `${Math.min(index, 5) * 60}ms` }}><button className="dish-image-button" onClick={() => setSelectedItem(item)} aria-label={`View ${item.name}`}><FoodImage item={item} className="dish-image" /><span className="image-gloss" /></button><div className="dish-content"><div className="dish-topline"><span className={`diet-badge ${item.dietary_type.toLowerCase()}`}><span className="diet-dot" />{dietaryLabel(item.dietary_type) || 'Chef’s pick'}</span><span className="time-label"><Clock3 size={13} />{item.variants[0]?.estimate_max_minutes} min</span></div><h4>{item.name}</h4><p>{item.description}</p><div className="dish-bottom"><div><span>FROM</span><strong>{formatMoney(itemPrice(item), currency)}</strong></div><button onClick={() => setSelectedItem(item)} aria-label={`Add ${item.name}`}><Plus size={19} strokeWidth={2.1} /></button></div></div></article>)}</div></section>) : <div className="empty-results"><Search size={27} /><h3>No dishes found</h3><p>Try another search or category.</p><button onClick={() => { setSearch(''); setCategory('all') }}>Clear search</button></div>}
        </section>
        <section className="help-banner"><div className="help-art"><Coffee size={34} strokeWidth={1.1} /></div><div><span className="eyebrow">HERE FOR YOU</span><h3>Need a hand?</h3><p>Our team is always happy to help at your table.</p></div><button onClick={() => requestService('WAITER')} disabled={!hasAccess || demo}>Call a waiter <ArrowRight size={17} /></button></section>{serviceMessage && <p className="service-message" role="status">{serviceMessage}</p>}
      </> : <section className="orders-page"><button className="back-link" onClick={() => setActiveTab('menu')}><ArrowLeft size={18} /> Back to menu</button><span className="eyebrow">YOUR TABLE</span><h1>Your orders</h1><p className="orders-intro">Good things are on their way. Check back here for updates.</p>{orderLoading && !orders.length && <div className="orders-loading">Loading your orders…</div>}{orderError && <p className="inline-error">{orderError}</p>}{!orders.length && !orderLoading && <div className="orders-empty"><ShoppingBag size={38} strokeWidth={1.3} /><h3>No orders yet</h3><p>Your freshly made picks will appear here.</p><button className="secondary-button" onClick={() => setActiveTab('menu')}>Explore the menu</button></div>}{orders.map(order => <article className="order-card" key={order.id}><div className="order-card-head"><div><span className="eyebrow">ORDER {order.display_ref || order.id.slice(0, 8)}</span><h3>Made with care</h3></div><span className="order-status">{order.lines.every(line => line.served_qty + line.cancelled_qty === line.quantity) ? 'Completed' : order.lines.some(line => line.ready_qty > 0) ? 'Ready soon' : order.lines.some(line => line.preparing_qty > 0) ? 'Being prepared' : 'Received'}</span></div>{order.lines.map(line => <div className="order-item" key={line.id}><span>{line.quantity} × {line.item_name}</span><span>{formatMoney((line.base_unit_paise + line.modifier_unit_paise) * line.quantity, currency)}</span></div>)}<div className="order-total"><span>Total</span><strong>{formatMoney(order.subtotal_paise, currency)}</strong></div></article>)}{!!orders.length && <div className="order-actions"><button onClick={() => requestService('WAITER')}><UtensilsCrossed size={17} /> Call a waiter</button><button onClick={() => requestService('BILL')}><MenuIcon size={17} /> Ask for the bill</button></div>}{serviceMessage && <p className="service-message" role="status">{serviceMessage}</p>}</section>}
    </main>
    <footer className="site-footer"><div><span className="footer-symbol"><UtensilsCrossed size={17} /></span><strong>{config.display_name}</strong><span>Good food, good company.</span></div><small>Powered by DineBridge</small></footer>
    {cartCount > 0 && activeTab === 'menu' && <div className="floating-cart"><button onClick={() => setCartOpen(true)}><span className="floating-cart-count">{cartCount}</span><span>View your order</span><strong>{formatMoney(subtotal, currency)}</strong><ArrowRight size={19} /></button></div>}
    <nav className="mobile-nav" aria-label="Main navigation"><button className={activeTab === 'menu' ? 'active' : ''} onClick={() => setActiveTab('menu')}><UtensilsCrossed size={19} /><span>Menu</span></button><button className={activeTab === 'orders' ? 'active' : ''} onClick={() => setActiveTab('orders')}><Clock3 size={19} /><span>Orders</span></button><button onClick={() => setCartOpen(true)}><ShoppingBag size={19} /><span>Basket{cartCount ? ` (${cartCount})` : ''}</span></button></nav>
    {selectedItem && <ItemSheet key={selectedItem.id} item={selectedItem} currency={currency} onClose={() => setSelectedItem(null)} onAdd={addItem} />}
    {cartOpen && <CartSheet cart={cart} currency={currency} orderingEnabled={menu.ordering_enabled} onClose={() => setCartOpen(false)} onQuantity={changeQuantity} onSubmit={submitOrder} busy={submitBusy} error={submitError} hasAccess={hasAccess} demoMode={demo} />}
  </div>
}
