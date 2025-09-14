// Quick test to verify database connection
const { PrismaClient } = require('@prisma/client');

async function testConnection() {
  const prisma = new PrismaClient();
  
  try {
    // Test basic connection
    await prisma.$connect();
    console.log('✅ Database connected successfully!');
    
    // Test a simple query
    const count = await prisma.podcastEpisode.count();
    console.log(`✅ Found ${count} podcast episodes in database`);
    
    // Test schema access
    const tables = await prisma.$queryRaw`
      SELECT tablename FROM pg_tables WHERE schemaname = 'public'
    `;
    console.log(`✅ Can access ${tables.length} tables in public schema`);
    
    console.log('\n🎉 All database tests passed!');
  } catch (error) {
    console.error('❌ Database connection failed:', error.message);
  } finally {
    await prisma.$disconnect();
  }
}

testConnection();