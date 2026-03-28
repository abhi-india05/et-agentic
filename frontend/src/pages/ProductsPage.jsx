import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { PackagePlus, Boxes, Search, X, Trash2 } from 'lucide-react'
import { api } from '../services/api.js'
import {
  LoadingState, ErrorState, SectionHeader, EmptyState,
  PaginationControls, Modal, Button,
} from '../components/UI.jsx'
import { fmt } from '../utils/fmt.js'

const PAGE_SIZE = 10

export default function ProductsPage() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Pagination state
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  // Filter state
  const [nameFilter, setNameFilter] = useState('')
  const [createdFrom, setCreatedFrom] = useState('')
  const [createdTo, setCreatedTo] = useState('')

  // Create form
  const [form, setForm] = useState({ name: '', description: '' })
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  // Delete modal
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async (p = page) => {
    setLoading(true)
    setError('')
    try {
      const { data, pagination } = await api.products({
        page: p,
        pageSize: PAGE_SIZE,
        name: nameFilter || undefined,
        createdFrom: createdFrom || undefined,
        createdTo: createdTo || undefined,
      })
      setItems(data || [])
      setTotal(pagination.total)
      setPage(pagination.page)
    } catch (e) {
      setError(e.message || 'Failed to load products')
    } finally {
      setLoading(false)
    }
  }, [page, nameFilter, createdFrom, createdTo])

  useEffect(() => { load(1) }, [nameFilter, createdFrom, createdTo]) // eslint-disable-line react-hooks/exhaustive-deps

  function handlePageChange(newPage) {
    load(newPage)
  }

  async function createProduct(e) {
    e.preventDefault()
    if (!form.name.trim()) {
      setFormError('Product name is required')
      return
    }
    setFormError('')
    setSaving(true)
    try {
      await api.createProduct({
        name: form.name.trim(),
        description: form.description.trim() || undefined,
      })
      setForm({ name: '', description: '' })
      await load(1)
      toast.success('Product created successfully')
    } catch (e) {
      setFormError(e.message || 'Failed to create product')
    } finally {
      setSaving(false)
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await api.deleteProduct(deleteTarget.product_id)
      setDeleteTarget(null)
      await load(page)
      toast.success('Product deleted successfully')
    } catch (e) {
      setError(e.message || 'Failed to delete product')
      setDeleteTarget(null)
    } finally {
      setDeleting(false)
    }
  }

  function clearFilters() {
    setNameFilter('')
    setCreatedFrom('')
    setCreatedTo('')
  }

  const hasFilters = nameFilter || createdFrom || createdTo

  return (
    <div className="space-y-6 animate-fade-up">
      <SectionHeader
        title="Products"
        subtitle="Create and manage product records (name + description)."
      />

      {/* ─── Create Product Form ──────────────────────────────── */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <PackagePlus className="w-4 h-4 text-accent" />
          <div className="text-sm font-display font-700 text-text">New product</div>
        </div>

        <form onSubmit={createProduct} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="block">
            <span className="text-xs text-muted font-mono block mb-1.5">Name *</span>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none"
              maxLength={200}
              placeholder="Product name"
            />
          </label>

          <label className="block">
            <span className="text-xs text-muted font-mono block mb-1.5">Description (optional)</span>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none min-h-[44px]"
              maxLength={5000}
              placeholder="Short description"
            />
          </label>

          <div className="md:col-span-2 flex items-center justify-between">
            {formError && <span className="text-xs text-danger font-mono">{formError}</span>}
            <div className="flex-1" />
            <button className="btn-primary disabled:opacity-50" disabled={saving}>
              {saving ? 'Creating…' : 'Create product'}
            </button>
          </div>
        </form>
      </div>

      {/* ─── Filters ──────────────────────────────────────────── */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <Search className="w-4 h-4 text-muted" />
          <div className="text-sm font-display font-700 text-text">Filters</div>
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="ml-auto text-xs text-muted hover:text-accent font-mono flex items-center gap-1 transition"
            >
              <X className="w-3 h-3" /> Clear
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <label className="block">
            <span className="text-xs text-muted font-mono block mb-1.5">Name search</span>
            <input
              value={nameFilter}
              onChange={(e) => setNameFilter(e.target.value)}
              className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none"
              placeholder="Search by name…"
            />
          </label>

          <label className="block">
            <span className="text-xs text-muted font-mono block mb-1.5">Created from</span>
            <input
              type="date"
              value={createdFrom}
              onChange={(e) => setCreatedFrom(e.target.value)}
              className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none"
            />
          </label>

          <label className="block">
            <span className="text-xs text-muted font-mono block mb-1.5">Created to</span>
            <input
              type="date"
              value={createdTo}
              onChange={(e) => setCreatedTo(e.target.value)}
              className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none"
            />
          </label>
        </div>
      </div>

      {/* ─── Product List ─────────────────────────────────────── */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <Boxes className="w-4 h-4 text-muted" />
          <div className="text-sm font-display font-700 text-text">Your products</div>
          <span className="text-xs text-muted font-mono ml-auto">{total} total</span>
        </div>

        {loading ? (
          <LoadingState message="Loading products…" />
        ) : error ? (
          <ErrorState message={error} onRetry={() => load(page)} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={Boxes}
            title="No products yet"
            description={hasFilters
              ? 'No products match your filters. Try different criteria.'
              : 'Create a product to store a description and reference it across workflows.'}
          />
        ) : (
          <>
            <div className="divide-y divide-border/60">
              {items.map((p) => (
                <div
                  key={p.product_id}
                  className="flex items-center justify-between gap-3 py-3 hover:bg-panel/40 rounded-lg px-2 transition group"
                >
                  <Link
                    to={`/products/${p.product_id}`}
                    className="flex-1 min-w-0"
                  >
                    <div className="text-sm text-text font-display">{p.name}</div>
                    <div className="text-xs text-muted font-mono truncate max-w-[520px]">
                      {p.description || 'No description'}
                    </div>
                    <div className="text-xs text-muted/60 font-mono mt-0.5">
                      Created {fmt.reltime(p.created_at)}
                      {p.is_deleted && (
                        <span className="ml-2 text-danger">(deleted)</span>
                      )}
                    </div>
                  </Link>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setDeleteTarget(p)}
                      className="opacity-0 group-hover:opacity-100 text-muted hover:text-danger transition p-1"
                      title="Delete product"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                    <Link
                      to={`/products/${p.product_id}`}
                      className="text-xs text-muted font-mono hover:text-accent transition"
                    >
                      View →
                    </Link>
                  </div>
                </div>
              ))}
            </div>

            <PaginationControls
              page={page}
              pageSize={PAGE_SIZE}
              total={total}
              onPageChange={handlePageChange}
            />
          </>
        )}
      </div>

      {/* ─── Delete Confirmation Modal ────────────────────────── */}
      <Modal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="Delete Product"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleteTarget(null)} disabled={deleting}>
              Cancel
            </Button>
            <Button variant="danger" onClick={confirmDelete} disabled={deleting}>
              {deleting ? 'Deleting…' : 'Delete'}
            </Button>
          </>
        }
      >
        <p>
          Are you sure you want to delete{' '}
          <strong className="text-text">{deleteTarget?.name}</strong>?
        </p>
        <p className="mt-2 text-xs text-muted">
          This performs a soft delete. The product will be marked as deleted but can be recovered.
        </p>
      </Modal>
    </div>
  )
}
