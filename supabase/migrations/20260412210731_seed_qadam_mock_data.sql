-- Mock data aligned with app/seed.py (static tables + stub review authors).

INSERT INTO buildings (id, name, short_name, description, latitude, longitude, floors, has_elevator, has_ramp, category) VALUES
('bldg-001', 'Block 1 - Sciences', 'Block 1', 'Main science building with laboratories and lecture halls', 51.0906, 71.3989, 4, true, true, 'academic'),
('bldg-002', 'Block 2 - Engineering', 'Block 2', 'Engineering and technology building', 51.0912, 71.3995, 4, true, true, 'academic'),
('bldg-003', 'Block 3 - Business School', 'Block 3', 'Graduate School of Business', 51.0898, 71.3982, 3, true, true, 'academic'),
('bldg-004', 'Library', 'Library', 'Main university library with study spaces', 51.0904, 71.4001, 3, true, true, 'library'),
('bldg-005', 'Student Center', 'Student Center', 'Student services, cafeterias, and recreation', 51.0910, 71.4008, 2, true, true, 'dining'),
('bldg-006', 'Dormitory A', 'Dorm A', 'Student residential building', 51.0920, 71.4015, 8, true, true, 'residential'),
('bldg-007', 'Sports Complex', 'Sports', 'Gymnasium, pool, and sports facilities', 51.0895, 71.4020, 2, false, true, 'sports'),
('bldg-008', 'Administration Building', 'Admin', 'University administration offices', 51.0900, 71.3975, 3, true, true, 'admin')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rooms (id, building_id, name, floor, type, capacity, accessible) VALUES
('room-001', 'bldg-001', '101', 1, 'classroom', 50, true),
('room-002', 'bldg-001', '102', 1, 'lab', 30, true),
('room-003', 'bldg-001', '201', 2, 'classroom', 80, true),
('room-004', 'bldg-001', '301', 3, 'lab', 25, true),
('room-005', 'bldg-002', '105', 1, 'classroom', 60, true),
('room-006', 'bldg-002', '210', 2, 'lab', 20, true),
('room-007', 'bldg-003', '101', 1, 'classroom', 100, true),
('room-008', 'bldg-004', 'Study Hall A', 1, 'study_room', 40, true),
('room-009', 'bldg-004', 'Study Hall B', 2, 'study_room', 30, true),
('room-010', 'bldg-004', 'Group Study 1', 2, 'study_room', 8, true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO campus_events (id, title, description, location, building_id, start_date, end_date, category, organizer, is_registration_required, registration_url) VALUES
('evt-001', 'Spring Career Fair 2026', 'Annual career fair featuring top employers from Kazakhstan and international companies.', 'Student Center, Main Hall', 'bldg-005', '2026-04-15T10:00:00Z', '2026-04-15T17:00:00Z', 'career', 'Career Center', true, 'https://nu.edu.kz/career-fair'),
('evt-002', 'AI & Machine Learning Workshop', 'Hands-on workshop on the latest AI technologies and their applications.', 'Block 2, Room 210', 'bldg-002', '2026-04-10T14:00:00Z', '2026-04-10T17:00:00Z', 'academic', 'Computer Science Department', true, NULL),
('evt-003', 'Nauryz Celebration', 'Traditional Kazakh New Year celebration with music, food, and cultural performances.', 'Campus Main Square', NULL, '2026-03-22T12:00:00Z', '2026-03-22T20:00:00Z', 'cultural', 'Student Government', false, NULL),
('evt-004', 'Basketball Tournament', 'Inter-department basketball competition. Come support your team!', 'Sports Complex, Main Gym', 'bldg-007', '2026-04-05T18:00:00Z', '2026-04-05T21:00:00Z', 'sports', 'Sports Club', false, NULL),
('evt-005', 'Guest Lecture: Future of Renewable Energy', 'Distinguished lecture by Dr. Sarah Chen on sustainable energy solutions.', 'Block 3, Auditorium', 'bldg-003', '2026-04-08T15:00:00Z', '2026-04-08T17:00:00Z', 'academic', 'School of Engineering', false, NULL),
('evt-006', 'Movie Night: Interstellar', 'Free outdoor movie screening. Bring your blankets!', 'Campus Amphitheater', NULL, '2026-04-12T20:00:00Z', '2026-04-12T23:00:00Z', 'social', 'Film Club', false, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO discounts (id, vendor_name, title, description, discount_percentage, category, valid_until, code, terms, is_verified) VALUES
('disc-001', 'Starbucks', '15% Off All Beverages', 'Show your student ID to get 15% off any drink at Starbucks campus location.', 15, 'food', '2026-12-31', NULL, 'Valid only at campus location. Cannot be combined with other offers.', true),
('disc-002', 'Cinema City', 'Student Movie Tickets - 50% Off', 'Half price movie tickets for students on weekdays.', 50, 'entertainment', '2026-06-30', 'STUDENT50', 'Valid Monday-Thursday. Not valid on holidays or special screenings.', true),
('disc-003', 'TechZone', '10% Off Electronics', 'Student discount on laptops, tablets, and accessories.', 10, 'shopping', '2026-08-31', 'NUSTUDENT10', 'Valid with student ID. Some exclusions apply.', true),
('disc-004', 'Fit Life Gym', 'Student Membership - 30% Off', 'Discounted monthly gym membership for NU students.', 30, 'services', '2026-12-31', NULL, 'Valid student ID required. 6-month minimum commitment.', true),
('disc-005', 'Pizza House', '20% Off Large Pizzas', 'Student special on all large pizzas.', 20, 'food', '2026-05-31', 'NUPIZZA20', 'Delivery and takeout only. Valid after 6 PM.', true),
('disc-006', 'Kazakh Railways', 'Student Travel Discount - 25% Off', 'Discounted train tickets for students traveling within Kazakhstan.', 25, 'travel', '2026-12-31', NULL, 'Valid with student ID. Economy class only.', true),
('disc-007', 'Campus Cafe', 'Free Coffee Upgrade', 'Get a free size upgrade on any coffee drink.', 0, 'food', '2026-04-30', NULL, 'Show Qadam app for discount.', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO study_rooms (id, building_id, building_name, name, floor, capacity, amenities, is_available, current_occupancy, noise_level) VALUES
('study-001', 'bldg-004', 'Library', 'Study Hall A', 1, 40, '["Wi-Fi", "Power Outlets", "Natural Light", "Whiteboard"]'::jsonb, true, 18, 'quiet'),
('study-002', 'bldg-004', 'Library', 'Study Hall B', 2, 30, '["Wi-Fi", "Power Outlets", "Projector"]'::jsonb, true, 25, 'quiet'),
('study-003', 'bldg-004', 'Library', 'Group Study 1', 2, 8, '["Wi-Fi", "Whiteboard", "TV Screen", "Power Outlets"]'::jsonb, false, 6, 'collaborative'),
('study-004', 'bldg-004', 'Library', 'Group Study 2', 2, 8, '["Wi-Fi", "Whiteboard", "TV Screen", "Power Outlets"]'::jsonb, true, 0, 'collaborative'),
('study-005', 'bldg-005', 'Student Center', 'Open Study Area', 1, 50, '["Wi-Fi", "Power Outlets", "Vending Machines"]'::jsonb, true, 35, 'moderate'),
('study-006', 'bldg-001', 'Block 1', 'Science Commons', 1, 20, '["Wi-Fi", "Power Outlets", "Lab Equipment Access"]'::jsonb, true, 8, 'moderate')
ON CONFLICT (id) DO NOTHING;

INSERT INTO users (id, email, password_hash, first_name, last_name, student_id) VALUES
('user-002', 'user-002@stub.internal', 'stub', 'Amir', 'K.', 'stub'),
('user-003', 'user-003@stub.internal', 'stub', 'Dana', 'S.', 'stub'),
('user-004', 'user-004@stub.internal', 'stub', 'Bekzat', 'T.', 'stub'),
('user-005', 'user-005@stub.internal', 'stub', 'Gulnara', 'M.', 'stub'),
('user-006', 'user-006@stub.internal', 'stub', 'Marat', 'A.', 'stub')
ON CONFLICT (id) DO NOTHING;

INSERT INTO reviews (id, user_id, target_id, target_type, target_name, rating, comment, sentiment, helpful, created_at) VALUES
('rev-001', 'user-002', 'bldg-004', 'building', 'Library', 5, 'Great study environment! The 3rd floor is perfect for quiet studying. Plenty of outlets and natural light.', 'positive', 24, '2026-03-28T14:30:00Z'::timestamptz),
('rev-002', 'user-003', 'bldg-005', 'cafe', 'Student Center Cafe', 4, 'Good food options and reasonable prices. Can get crowded during lunch hours though.', 'positive', 15, '2026-03-25T12:15:00Z'::timestamptz),
('rev-003', 'user-004', 'room-010', 'room', 'Group Study Room 1', 3, 'Room is nice but booking system is confusing. Wish it was easier to reserve.', 'neutral', 8, '2026-03-20T16:45:00Z'::timestamptz),
('rev-004', 'user-005', 'bldg-007', 'building', 'Sports Complex', 5, 'Excellent facilities! The swimming pool is well maintained and the gym has modern equipment.', 'positive', 32, '2026-03-18T09:00:00Z'::timestamptz),
('rev-005', 'user-006', 'bldg-001', 'building', 'Block 1 - Sciences', 4, 'Labs are well-equipped. Sometimes elevators are slow during class transitions.', 'positive', 11, '2026-03-15T11:30:00Z'::timestamptz)
ON CONFLICT (id) DO NOTHING;
