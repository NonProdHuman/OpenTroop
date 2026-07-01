"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { FunctionalRole, FunctionalRolePermission, Permission } from "@/types/api"

export function useFunctionalRoles() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "functional-roles"],
    queryFn: () => request<FunctionalRole[]>("/functional-roles"),
    enabled: Boolean(activeTenantId),
  })
}

export function useFunctionalRole(roleId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "functional-roles", roleId],
    queryFn: () => request<FunctionalRole>(`/functional-roles/${roleId}`),
    enabled: roleId !== null && Boolean(activeTenantId),
  })
}

export function useCreateFunctionalRole() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; slug: string }) =>
      request<FunctionalRole>("/functional-roles", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "functional-roles"] })
    },
  })
}

export function useUpdateFunctionalRole() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name?: string } }) =>
      request<FunctionalRole>(`/functional-roles/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "functional-roles"] })
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "functional-roles", id] })
    },
  })
}

export function useDeleteFunctionalRole() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => request(`/functional-roles/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "functional-roles"] })
    },
  })
}

// ── Permissions on a functional role ─────────────────────────────────────────

export function useFunctionalRolePermissions(roleId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "functional-role-permissions", roleId],
    queryFn: () =>
      request<FunctionalRolePermission[]>(`/functional-roles/${roleId}/permissions`),
    enabled: roleId !== null && Boolean(activeTenantId),
  })
}

export function useGrantFunctionalRolePermission() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ roleId, permission }: { roleId: string; permission: Permission }) =>
      request<FunctionalRolePermission>(`/functional-roles/${roleId}/permissions`, {
        method: "POST",
        body: JSON.stringify({ permission }),
      }),
    onSuccess: (_data, { roleId }) => {
      queryClient.invalidateQueries({
        queryKey: [activeTenantId, "functional-role-permissions", roleId],
      })
    },
  })
}

export function useRevokeFunctionalRolePermission() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ roleId, permission }: { roleId: string; permission: Permission }) =>
      request(`/functional-roles/${roleId}/permissions/${permission}`, { method: "DELETE" }),
    onSuccess: (_data, { roleId }) => {
      queryClient.invalidateQueries({
        queryKey: [activeTenantId, "functional-role-permissions", roleId],
      })
    },
  })
}
