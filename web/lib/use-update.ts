"use client";

import { useQuery } from "@tanstack/react-query";
import { getUpdate } from "./api";

const SIX_HOURS = 6 * 60 * 60 * 1000;

/**
 * Whether a newer Voxa is out. The server asks PyPI at most once a day and answers from what
 * it kept otherwise, so asking it every few hours costs nothing; a console left open for days
 * still hears of a release.
 */
export function useUpdateStatus() {
  return useQuery({
    queryKey: ["update"],
    queryFn: getUpdate,
    staleTime: SIX_HOURS,
    refetchInterval: SIX_HOURS,
    retry: false,
  });
}
