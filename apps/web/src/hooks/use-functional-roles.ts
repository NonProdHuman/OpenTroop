"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { FunctionalRole, FunctionalRolePermission, Permission } from "@/types/api"

export function useFunctionalRoles() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.functionalRoles(activeTenantId),
    queryFn: () => request<FunctionalRole[]>("/functional-roles"),
    enabled: Boolean(activeTenantId),
  })
}

export function useFunctionalRole(roleId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.functionalRole(activeTenantId, roleId),
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
      queryClient.invalidateQueries({ queryKey: queryKeys.functionalRoles(activeTenantId) })
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
      queryClient.invalidateQueries({ queryKey: queryKeys.functionalRoles(activeTenantId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.functionalRole(activeTenantId, id) })
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
      queryClient.invalidateQueries({ queryKey: queryKeys.functionalRoles(activeTenantId) })
    },
  })
}

// ── Permissions on a functional role ─────────────────────────────────────────

export function useFunctionalRolePermissions(roleId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.functionalRolePermissions(activeTenantId, roleId),
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
        queryKey: queryKeys.functionalRolePermissions(activeTenantId, roleId),
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
        queryKey: queryKeys.functionalRolePermissions(activeTenantId, roleId),
      })
    },
  })
}
