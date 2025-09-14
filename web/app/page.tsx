/**
 * Home page - redirects to dashboard inbox
 * Entry point for the application
 */

import { redirect } from "next/navigation"

export default function HomePage() {
  redirect("/inbox")
}