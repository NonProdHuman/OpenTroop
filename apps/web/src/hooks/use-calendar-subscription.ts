"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type { CalendarSubscriptionRead } from "@/types/api"
import { toast } from "sonner"

export function useCalendarSubscription() {
  const { request } = useApi()
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: ["calendar-subscription"],
    queryFn: () =>
      request<CalendarSubscriptionRead>("/calendar/subscription", {
        method: "POST",
      }),
    staleTime: Infinity,
  })

  const rotate = useMutation({
    mutationFn: () =>
      request<CalendarSubscriptionRead>("/calendar/subscription", {
        method: "DELETE",
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["calendar-subscription"], data)
      toast.success("Calendar feed link reset successfully")
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed to reset calendar link")
    },
  })

  return {
    subscription: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
    rotate: rotate.mutate,
    isRotating: rotate.isPending,
  }
}
