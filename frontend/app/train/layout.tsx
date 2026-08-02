"use client";

import { useEffect } from "react";
import AuthHeader from "@/components/AuthHeader";
import { getAnonId } from "@/lib/auth";

export default function TrainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Ensure anon-id is set on any /train/* page.
  useEffect(() => {
    getAnonId();
  }, []);

  return (
    <>
      <AuthHeader />
      {children}
    </>
  );
}
