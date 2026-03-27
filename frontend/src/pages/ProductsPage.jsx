import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { PackagePlus, Boxes } from 'lucide-react'
import { api } from '../utils/api.js'
import { LoadingState, ErrorState, SectionHeader, EmptyState } from '../components/UI.jsx'

export default function ProductsPage() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ name: '', description: '' })
  const [saving, setSaving] = useState(false)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const res = await api.products()
      setItems(res || [])
    } catch (e) {
      setError(e.message || 'Failed to load products')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function createProduct(e) {
    e.preventDefault()
    if (!form.name.trim()) return
    setSaving(true)
    try {
      await api.createProduct({
        name: form.name,
        description: form.description,
      })
      setForm({ name: '', description: '' })
      await load()
    } catch (e) {
      setError(e.message || 'Failed to create product')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState message="Loading productsâ€¦" />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <div className="space-y-6 animate-fade-up">
      <SectionHeader
        title="Products"
        subtitle="Create and manage product records (name + description)."
      />

      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <PackagePlus className="w-4 h-4 text-accent" />
          <div className="text-sm font-display font-700 text-text">New product</div>
        </div>

        <form onSubmit={createProduct} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="block">
            <span className="text-xs text-muted font-mono block mb-1.5">Name</span>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none"
              maxLength={200}
            />
          </label>

          <label className="block">
            <span className="text-xs text-muted font-mono block mb-1.5">Description (optional)</span>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none min-h-[44px]"
              maxLength={5000}
            />
          </label>

          <div className="md:col-span-2 flex justify-end">
            <button className="btn-primary disabled:opacity-50" disabled={saving}>
              {saving ? 'Creatingâ€¦' : 'Create product'}
            </button>
          </div>
        </form>
      </div>

      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <Boxes className="w-4 h-4 text-muted" />
          <div className="text-sm font-display font-700 text-text">Your products</div>
        </div>

        {items.length === 0 ? (
          <EmptyState
            icon={Boxes}
            title="No products yet"
            description="Create a product to store a description and reference it across workflows."
          />
        ) : (
          <div className="divide-y divide-border/60">
            {items.map((p) => (
              <Link
                key={p.product_id}
                to={`/products/${p.product_id}`}
                className="block py-3 hover:bg-panel/40 rounded-lg px-2 transition"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm text-text font-display">{p.name}</div>
                    <div className="text-xs text-muted font-mono truncate max-w-[520px]">
                      {p.description || 'No description'}
                    </div>
                  </div>
                  <span className="text-xs text-muted font-mono">View</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
