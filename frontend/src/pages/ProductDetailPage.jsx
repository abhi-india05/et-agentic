import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { ArrowLeft, Save } from 'lucide-react'
import { api } from '../utils/api.js'
import { LoadingState, ErrorState, SectionHeader } from '../components/UI.jsx'

export default function ProductDetailPage() {
  const { productId } = useParams()
  const navigate = useNavigate()
  const [product, setProduct] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ name: '', description: '' })

  async function load() {
    setLoading(true)
    setError('')
    try {
      const res = await api.product(productId)
      setProduct(res)
      setForm({ name: res.name || '', description: res.description || '' })
    } catch (e) {
      setError(e.message || 'Failed to load product')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [productId])

  async function save(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const updated = await api.updateProduct(productId, {
        name: form.name,
        description: form.description,
      })
      setProduct(updated)
      setForm({ name: updated.name || '', description: updated.description || '' })
    } catch (e) {
      setError(e.message || 'Failed to update product')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState message="Loading productâ€¦" />
  if (error) return <ErrorState message={error} onRetry={load} />
  if (!product) return null

  return (
    <div className="space-y-6 animate-fade-up">
      <SectionHeader
        title={product.name}
        subtitle="Edit the product description and save changes."
        action={
          <button className="btn-ghost text-xs" onClick={() => navigate(-1)}>
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
        }
      />

      <div className="card">
        <form onSubmit={save} className="space-y-4">
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
            <span className="text-xs text-muted font-mono block mb-1.5">Description</span>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none min-h-32"
              maxLength={5000}
            />
          </label>

          <div className="flex items-center justify-between">
            <Link to="/products" className="text-xs text-muted font-mono hover:text-text transition">
              <ArrowLeft className="w-3.5 h-3.5 inline-block mr-1" />
              All products
            </Link>
            <button className="btn-primary disabled:opacity-50 flex items-center gap-2" disabled={saving}>
              <Save className="w-4 h-4" />
              {saving ? 'Savingâ€¦' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

