"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type {
  PlatformAdmin,
  PlatformAdminGrantInput,
  Tenant,
  TenantAdmin,
  TenantAdminInviteInput,
  TenantAdminInviteResult,
  TenantProvisioned,
  TenantProvisionInput,
} from "@/types/api"

const tenantsKey = ["platform", "tenants"] as const
const tenantKey = (id: string) => ["platform", "tenant", id] as const
const adminsKey = (id: string) => ["platform", "tenant", id, "admins"] as const
const platformAdminsKey = ["platform", "admins"] as const

export function useTenants() {
  const { request } = useApi()
  return useQuery({
    queryKey: tenantsKey,
    queryFn: () => request<Tenant[]>("/platform/tenants"),
  })
}

export function useTenant(id: string) {
  const { request } = useApi()
  return useQuery({
    queryKey: tenantKey(id),
    queryFn: () => request<Tenant>(`/platform/tenants/${id}`),
    enabled: Boolean(id),
  })
}

export function useTenantAdmins(id: string) {
  const { request } = useApi()
  return useQuery({
    queryKey: adminsKey(id),
    queryFn: () => request<TenantAdmin[]>(`/platform/tenants/${id}/admins`),
    enabled: Boolean(id),
  })
}

export function useCreateTenant() {
  const { request } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: TenantProvisionInput) =>
      request<TenantProvisioned>("/platform/tenants", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: tenantsKey }),
  })
}

export function useSetTenantSuspended(id: string) {
  const { request } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (suspend: boolean) =>
      request<Tenant>(`/platform/tenants/${id}/${suspend ? "suspend" : "unsuspend"}`, {
        method: "POST",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: tenantKey(id) })
      qc.invalidateQueries({ queryKey: tenantsKey })
    },
  })
}

export function useInviteTenantAdmin(id: string) {
  const { request } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: TenantAdminInviteInput) =>
      request<TenantAdminInviteResult>(`/platform/tenants/${id}/admins`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminsKey(id) }),
  })
}

export function useRevokeTenantAdmin(id: string) {
  const { request } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (memberId: string) =>
      request<void>(`/platform/tenants/${id}/admins/${memberId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminsKey(id) }),
  })
}

export function useExportTenant(id: string) {
  const { request } = useApi()
  const qc = useQueryClient()
  return useMutation({
    // The bundle is the troop's complete data — the caller downloads it as a
    // file. Exporting stamps last_export_at, which arms the delete gate.
    mutationFn: () => request<Record<string, unknown>>(`/platform/tenants/${id}/export`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: tenantKey(id) })
      qc.invalidateQueries({ queryKey: tenantsKey })
    },
  })
}

export function useDeleteTenant(id: string) {
  const { request } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (confirmSlug: string) =>
      request<void>(`/platform/tenants/${id}`, {
        method: "DELETE",
        body: JSON.stringify({ confirm_slug: confirmSlug }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: tenantsKey }),
  })
}

// ── Platform administrators (the global tier) ────────────────────────────────

export function usePlatformAdmins() {
  const { request } = useApi()
  return useQuery({
    queryKey: platformAdminsKey,
    queryFn: () => request<PlatformAdmin[]>("/platform/admins"),
  })
}

export function useGrantPlatformAdmin() {
  const { request } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: PlatformAdminGrantInput) =>
      request<PlatformAdmin>("/platform/admins", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: platformAdminsKey }),
  })
}

export function useRevokePlatformAdmin() {
  const { request } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) =>
      request<void>(`/platform/admins/${userId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: platformAdminsKey }),
  })
}
