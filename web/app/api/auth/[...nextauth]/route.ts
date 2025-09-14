import NextAuth from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"
import bcrypt from "bcryptjs"
import { AUTH_CONFIG } from "@/lib/auth-config"

// Use hardcoded hash from config to avoid env var $ parsing issues
const ADMIN_PASSWORD_HASH = AUTH_CONFIG.ADMIN_PASSWORD_HASH

const handler = NextAuth({
  providers: [
    CredentialsProvider({
      name: "credentials",
      credentials: {
        username: { label: "Username", type: "text" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials) {
        console.log('Auth attempt:', {
          username: credentials?.username,
          passwordProvided: !!credentials?.password,
          hashFromEnv: ADMIN_PASSWORD_HASH?.substring(0, 20) + '...',
          hashExists: !!ADMIN_PASSWORD_HASH
        });
        
        // Single admin user
        if (
          credentials?.username === "admin" && 
          credentials?.password &&
          ADMIN_PASSWORD_HASH &&
          await bcrypt.compare(credentials.password, ADMIN_PASSWORD_HASH)
        ) {
          console.log('Auth successful');
          return { id: "1", name: "Admin", email: "admin@wdfwatch.local" }
        }
        console.log('Auth failed');
        return null
      }
    })
  ],
  pages: {
    signIn: "/login",
  },
  callbacks: {
    async session({ session }) {
      // Add any custom session data
      return session
    }
  }
})

export { handler as GET, handler as POST }