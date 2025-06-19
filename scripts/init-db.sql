-- =====================================================
-- GradeInsight Multi-Tenant Database Initialization
-- =====================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- TENANT MANAGEMENT
-- =====================================================

-- Tenant registry table
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_key VARCHAR(100) UNIQUE NOT NULL,
    tenant_name VARCHAR(255) NOT NULL,
    domain VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'inactive')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- APPLICATION TABLES (Multi-Tenant)
-- =====================================================

-- Students table
CREATE TABLE IF NOT EXISTS students (
    email VARCHAR(255) NOT NULL,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    student_number VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (email, tenant_id)
);

-- Tags table
CREATE TABLE IF NOT EXISTS tags (
    id SERIAL,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    color VARCHAR(7) DEFAULT '#3B82F6',
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, tenant_id),
    UNIQUE (tenant_id, name)
);

-- Assignments table
CREATE TABLE IF NOT EXISTS assignments (
    id SERIAL,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255),
    date DATE,
    max_points DECIMAL(8,2) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, tenant_id)
);

-- Grades table
CREATE TABLE IF NOT EXISTS grades (
    id SERIAL,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    assignment_id INTEGER NOT NULL,
    score DECIMAL(8,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, tenant_id),
    FOREIGN KEY (email, tenant_id) REFERENCES students(email, tenant_id) ON DELETE CASCADE,
    FOREIGN KEY (assignment_id, tenant_id) REFERENCES assignments(id, tenant_id) ON DELETE CASCADE,
    UNIQUE (tenant_id, email, assignment_id)
);

-- Association table for many-to-many relationship between assignments and tags
CREATE TABLE IF NOT EXISTS assignment_tags (
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    assignment_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, assignment_id, tag_id),
    FOREIGN KEY (assignment_id, tenant_id) REFERENCES assignments(id, tenant_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id, tenant_id) REFERENCES tags(id, tenant_id) ON DELETE CASCADE
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Tenant indexes
CREATE INDEX IF NOT EXISTS idx_tenants_tenant_key ON tenants(tenant_key);
CREATE INDEX IF NOT EXISTS idx_tenants_domain ON tenants(domain);
CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status);

-- Student indexes
CREATE INDEX IF NOT EXISTS idx_students_tenant_id ON students(tenant_id);
CREATE INDEX IF NOT EXISTS idx_students_email ON students(email);
CREATE INDEX IF NOT EXISTS idx_students_name ON students(tenant_id, last_name, first_name);

-- Tag indexes
CREATE INDEX IF NOT EXISTS idx_tags_tenant_id ON tags(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(tenant_id, name);

-- Assignment indexes
CREATE INDEX IF NOT EXISTS idx_assignments_tenant_id ON assignments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_assignments_date ON assignments(tenant_id, date);
CREATE INDEX IF NOT EXISTS idx_assignments_name ON assignments(tenant_id, name);

-- Grade indexes
CREATE INDEX IF NOT EXISTS idx_grades_tenant_id ON grades(tenant_id);
CREATE INDEX IF NOT EXISTS idx_grades_student ON grades(tenant_id, email);
CREATE INDEX IF NOT EXISTS idx_grades_assignment ON grades(tenant_id, assignment_id);

-- Assignment tags indexes
CREATE INDEX IF NOT EXISTS idx_assignment_tags_assignment ON assignment_tags(tenant_id, assignment_id);
CREATE INDEX IF NOT EXISTS idx_assignment_tags_tag ON assignment_tags(tenant_id, tag_id);

-- =====================================================
-- ROW LEVEL SECURITY (Optional - for extra security)
-- =====================================================

-- Enable RLS on all tables
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE grades ENABLE ROW LEVEL SECURITY;
ALTER TABLE assignment_tags ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- SAMPLE DATA FOR DEVELOPMENT
-- =====================================================

-- Insert sample tenants
INSERT INTO tenants (tenant_key, tenant_name, domain) 
VALUES 
    ('demo-school', 'Demo Elementary School', 'demo.gradeinsight.com'),
    ('test-academy', 'Test Academy', 'test.gradeinsight.com')
ON CONFLICT (tenant_key) DO NOTHING;

-- Sample data for demo-school tenant
DO $$
DECLARE
    demo_tenant_id UUID;
    test_tenant_id UUID;
BEGIN
    -- Get tenant IDs
    SELECT id INTO demo_tenant_id FROM tenants WHERE tenant_key = 'demo-school';
    SELECT id INTO test_tenant_id FROM tenants WHERE tenant_key = 'test-academy';
    
    -- Sample students for demo-school
    INSERT INTO students (email, tenant_id, first_name, last_name, student_number) VALUES
        ('john.doe@demo.com', demo_tenant_id, 'John', 'Doe', 'STU001'),
        ('jane.smith@demo.com', demo_tenant_id, 'Jane', 'Smith', 'STU002'),
        ('bob.johnson@demo.com', demo_tenant_id, 'Bob', 'Johnson', 'STU003')
    ON CONFLICT DO NOTHING;
    
    -- Sample tags for demo-school
    INSERT INTO tags (tenant_id, name, color, description) VALUES
        (demo_tenant_id, 'Math', '#FF6B6B', 'Mathematics assignments'),
        (demo_tenant_id, 'Science', '#4ECDC4', 'Science related work'),
        (demo_tenant_id, 'Homework', '#45B7D1', 'Daily homework assignments'),
        (demo_tenant_id, 'Quiz', '#96CEB4', 'Quick assessments')
    ON CONFLICT DO NOTHING;
    
    -- Sample assignments for demo-school
    INSERT INTO assignments (tenant_id, name, date, max_points, description) VALUES
        (demo_tenant_id, 'Math Quiz 1', '2024-01-15', 100.0, 'Basic arithmetic quiz'),
        (demo_tenant_id, 'Science Project', '2024-01-20', 50.0, 'Solar system model'),
        (demo_tenant_id, 'Math Homework', '2024-01-10', 25.0, 'Chapter 3 exercises')
    ON CONFLICT DO NOTHING;
    
END $$;

-- =====================================================
-- HELPER FUNCTIONS
-- =====================================================

-- Function to get tenant ID by tenant key
CREATE OR REPLACE FUNCTION get_tenant_id(tenant_key_param VARCHAR)
RETURNS UUID AS $$
DECLARE
    tenant_uuid UUID;
BEGIN
    SELECT id INTO tenant_uuid FROM tenants WHERE tenant_key = tenant_key_param AND status = 'active';
    RETURN tenant_uuid;
END;
$$ LANGUAGE plpgsql;

-- Function to create a new tenant
CREATE OR REPLACE FUNCTION create_tenant(tenant_key_param VARCHAR, tenant_name_param VARCHAR, domain_param VARCHAR DEFAULT NULL)
RETURNS UUID AS $$
DECLARE
    new_tenant_id UUID;
BEGIN
    INSERT INTO tenants (tenant_key, tenant_name, domain)
    VALUES (tenant_key_param, tenant_name_param, domain_param)
    RETURNING id INTO new_tenant_id;
    
    RETURN new_tenant_id;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- TRIGGERS FOR UPDATED_AT
-- =====================================================

-- Function to update the updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_students_updated_at BEFORE UPDATE ON students FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_assignments_updated_at BEFORE UPDATE ON assignments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_grades_updated_at BEFORE UPDATE ON grades FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- COMPLETION MESSAGE
-- =====================================================

DO $$
BEGIN
    RAISE NOTICE '==============================================';
    RAISE NOTICE 'GradeInsight Multi-Tenant Database Setup Complete!';
    RAISE NOTICE '==============================================';
    RAISE NOTICE 'Created tables: tenants, students, tags, assignments, grades, assignment_tags';
    RAISE NOTICE 'Created indexes for performance optimization';
    RAISE NOTICE 'Created helper functions: get_tenant_id(), create_tenant()';
    RAISE NOTICE 'Inserted sample data for development';
    RAISE NOTICE 'Row Level Security enabled for tenant isolation';
    RAISE NOTICE '==============================================';
END $$;
