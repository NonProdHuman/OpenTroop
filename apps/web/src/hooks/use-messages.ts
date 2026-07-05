"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type {
  InboxPage,
  Message,
  MessageCreate,
  MessageDetail,
  MessageWithPreview,
  RecipientPreviewEntry,
} from "@/types/api"

export function useMessages(enabled = true) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.messages(activeTenantId),
    queryFn: () => request<Message[]>("/messages"),
    enabled: enabled && Boolean(activeTenantId),
  })
}

export function useMessage(id: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.message(activeTenantId, id),
    queryFn: () => request<MessageDetail>(`/messages/${id}`),
    enabled: id !== null && Boolean(activeTenantId),
  })
}

export function useRecipientPreview(id: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.messagePreview(activeTenantId, id),
    queryFn: () => request<RecipientPreviewEntry[]>(`/messages/${id}/recipients/preview`),
    enabled: id !== null && Boolean(activeTenantId),
  })
}

export function useInbox() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.inbox(activeTenantId),
    queryFn: () => request<InboxPage>("/messages/inbox"),
    enabled: Boolean(activeTenantId),
  })
}

export function useCreateMessage() {
  const { request } = useApi()
  const queryClient = useQueryClient()
  const { activeTenantId } = useActiveTenant()
  return useMutation({
    mutationFn: (data: MessageCreate) =>
      request<MessageWithPreview>("/messages", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.messages(activeTenantId) }),
  })
}

export function useSendMessage() {
  const { request } = useApi()
  const queryClient = useQueryClient()
  const { activeTenantId } = useActiveTenant()
  return useMutation({
    mutationFn: (id: string) =>
      request<MessageDetail>(`/messages/${id}/send`, { method: "POST" }),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.messages(activeTenantId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.message(activeTenantId, id) })
    },
  })
}

export function useMarkInboxRead() {
  const { request } = useApi()
  const queryClient = useQueryClient()
  const { activeTenantId } = useActiveTenant()
  return useMutation({
    mutationFn: (recipientId: string) =>
      request(`/messages/inbox/${recipientId}/read`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.inbox(activeTenantId) }),
  })
}
