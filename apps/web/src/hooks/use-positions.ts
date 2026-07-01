"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { Position, PositionFunctionalRole } from "@/types/api"

export function usePositions() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "positions"],
    queryFn: () => request<Position[]>("/positions"),
    enabled: Boolean(activeTenantId),
  })
}

export function usePosition(positionId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "positions", positionId],
    queryFn: () => request<Position>(`/positions/${positionId}`),
    enabled: positionId !== null && Boolean(activeTenantId),
  })
}

export function useCreatePosition() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; slug: string; applies_to?: string; sort_order?: number }) =>
      request<Position>("/positions", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "positions"] })
    },
  })
}

export function useUpdatePosition() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: { name?: string; applies_to?: string; sort_order?: number }
    }) => request<Position>(`/positions/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "positions"] })
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "positions", id] })
    },
  })
}

export function useDeletePosition() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => request(`/positions/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "positions"] })
    },
  })
}

// ── Position ↔ Functional role mapping ───────────────────────────────────────

export function usePositionFunctionalRoles(positionId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "position-functional-roles", positionId],
    queryFn: () =>
      request<PositionFunctionalRole[]>(`/positions/${positionId}/functional-roles`),
    enabled: positionId !== null && Boolean(activeTenantId),
  })
}

export function useAttachFunctionalRole() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      positionId,
      functionalRoleId,
    }: {
      positionId: string
      functionalRoleId: string
    }) =>
      request<PositionFunctionalRole>(`/positions/${positionId}/functional-roles`, {
        method: "POST",
        body: JSON.stringify({ functional_role_id: functionalRoleId }),
      }),
    onSuccess: (_data, { positionId }) => {
      queryClient.invalidateQueries({
        queryKey: [activeTenantId, "position-functional-roles", positionId],
      })
    },
  })
}

export function useDetachFunctionalRole() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      positionId,
      functionalRoleId,
    }: {
      positionId: string
      functionalRoleId: string
    }) =>
      request(`/positions/${positionId}/functional-roles/${functionalRoleId}`, {
        method: "DELETE",
      }),
    onSuccess: (_data, { positionId }) => {
      queryClient.invalidateQueries({
        queryKey: [activeTenantId, "position-functional-roles", positionId],
      })
    },
  })
}
