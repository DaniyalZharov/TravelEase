-- ============================================================
-- TravelEase Complete Database Schema + Seed Data
-- ISTE 430 Group 5
-- Run this entire file in HeidiSQL before launching app.py
-- ============================================================

-- Fresh demo database only. This script never drops an existing database.

CREATE DATABASE TravelEaseDemo
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

USE TravelEaseDemo;

-- ============================================================
-- TABLES
-- ============================================================

CREATE TABLE USER (
    UserID      INT AUTO_INCREMENT PRIMARY KEY,
    Name        VARCHAR(100) NOT NULL,
    Email       VARCHAR(150) UNIQUE NOT NULL,
    Nationality VARCHAR(50)  NOT NULL,
    PasswordHash VARCHAR(255) NULL
);

CREATE TABLE COUNTRY (
    CountryCode CHAR(2)      PRIMARY KEY,
    CountryName VARCHAR(100),
    Region      VARCHAR(50),
    Currency    VARCHAR(50)
);

CREATE TABLE DESTINATION (
    DestinationID INT AUTO_INCREMENT PRIMARY KEY,
    Description   TEXT,
    City          VARCHAR(100),
    CountryCode   CHAR(2),
    FOREIGN KEY (CountryCode) REFERENCES COUNTRY(CountryCode)
);

CREATE TABLE TRIP (
    TripID        INT AUTO_INCREMENT PRIMARY KEY,
    TripName      VARCHAR(100),
    StartDate     DATE,
    EndDate       DATE,
    Status        ENUM('Planning','Confirmed','Completed') DEFAULT 'Planning',
    UserID        INT,
    DestinationID INT,
    FOREIGN KEY (UserID)        REFERENCES USER(UserID),
    FOREIGN KEY (DestinationID) REFERENCES DESTINATION(DestinationID)
);

CREATE TABLE BOOKING (
    BookingID   INT AUTO_INCREMENT PRIMARY KEY,
    BookingType ENUM('Flight','Hotel'),
    BookingDate DATE,
    Status      VARCHAR(50),
    TotalPrice  DECIMAL(10,2) DEFAULT 0,
    TripID      INT,
    FOREIGN KEY (TripID) REFERENCES TRIP(TripID)
);

CREATE TABLE FLIGHT (
    FlightID      INT AUTO_INCREMENT PRIMARY KEY,
    Airline       VARCHAR(100),
    DepartureCity VARCHAR(100),
    ArrivalCity   VARCHAR(100),
    DepartureTime DATETIME,
    ArrivalTime   DATETIME,
    Price         DECIMAL(10,2),
    BookingID     INT,
    FOREIGN KEY (BookingID) REFERENCES BOOKING(BookingID)
);

CREATE TABLE HOTEL (
    HotelID       INT AUTO_INCREMENT PRIMARY KEY,
    HotelName     VARCHAR(100),
    Location      VARCHAR(100),
    CheckInDate   DATE,
    CheckOutDate  DATE,
    PricePerNight DECIMAL(10,2),
    BookingID     INT,
    FOREIGN KEY (BookingID) REFERENCES BOOKING(BookingID)
);

CREATE TABLE SEASON (
    SeasonID      INT AUTO_INCREMENT PRIMARY KEY,
    SeasonName    ENUM('Winter','Spring','Summer','Fall'),
    DestinationID INT,
    FOREIGN KEY (DestinationID) REFERENCES DESTINATION(DestinationID)
);

CREATE TABLE VISAREQUIREMENT (
    CountryCode    CHAR(2),
    VisaType       VARCHAR(50),
    Requirements   TEXT,
    ProcessingTime INT,
    PRIMARY KEY (CountryCode, VisaType),
    FOREIGN KEY (CountryCode) REFERENCES COUNTRY(CountryCode)
);

CREATE TABLE RECOMMENDATION (
    DestinationID   INT,
    SeasonID        INT,
    RecCategory     VARCHAR(50),
    RecDescription  TEXT,
    PopularityScore INT CHECK (PopularityScore BETWEEN 1 AND 100),
    PRIMARY KEY (DestinationID, SeasonID),
    FOREIGN KEY (DestinationID) REFERENCES DESTINATION(DestinationID),
    FOREIGN KEY (SeasonID)      REFERENCES SEASON(SeasonID)
);

-- ============================================================
-- SEED DATA
-- ============================================================

INSERT INTO USER (Name, Email, Nationality) VALUES
('Alex Morgan', 'alex@example.com', 'Demo'),
('Jordan Lee', 'jordan@example.com', 'Demo'),
('Sam Taylor', 'sam@example.com', 'Demo');

INSERT INTO COUNTRY VALUES
('AE', 'United Arab Emirates', 'Middle East',   'AED'),
('GB', 'United Kingdom',       'Europe',        'GBP'),
('JP', 'Japan',                'Asia',          'JPY'),
('US', 'United States',        'North America', 'USD'),
('FR', 'France',               'Europe',        'EUR'),
('TR', 'Turkey',               'Middle East',   'TRY'),
('TH', 'Thailand',             'Asia',          'THB');

INSERT INTO DESTINATION (Description, City, CountryCode) VALUES
('Modern city with iconic skyscrapers and luxury experiences.',      'Dubai',    'AE'),
('Historic capital with world-class museums and culture.',           'London',   'GB'),
('Ancient temples and vibrant street life.',                         'Tokyo',    'JP'),
('The city that never sleeps.',                                      'New York', 'US'),
('City of lights, art and the Eiffel Tower.',                        'Paris',    'FR'),
('Where East meets West.',                                           'Istanbul', 'TR'),
('Tropical beaches and incredible street food.',                     'Bangkok',  'TH');

INSERT INTO TRIP (TripName, StartDate, EndDate, Status, UserID, DestinationID) VALUES
('Summer Europe Trip', '2026-06-01', '2026-06-15', 'Confirmed', 1, 2),
('Tokyo Adventure',    '2026-07-10', '2026-07-25', 'Planning',  1, 3),
('Dubai Getaway',      '2026-09-05', '2026-09-12', 'Planning',  1, 1);

INSERT INTO BOOKING (BookingType, BookingDate, Status, TotalPrice, TripID) VALUES
('Flight', '2026-04-17', 'Confirmed', 850.00,  1),
('Hotel',  '2026-04-17', 'Confirmed', 1500.00, 1);

INSERT INTO FLIGHT (Airline, DepartureCity, ArrivalCity, DepartureTime, ArrivalTime, Price, BookingID) VALUES
('Emirates', 'Dubai', 'London', '2026-06-01 08:00:00', '2026-06-01 12:30:00', 850.00, 1);

INSERT INTO HOTEL (HotelName, Location, CheckInDate, CheckOutDate, PricePerNight, BookingID) VALUES
('The Ritz London', 'London, UK', '2026-06-01', '2026-06-11', 150.00, 2);

INSERT INTO SEASON (SeasonName, DestinationID) VALUES
('Summer', 1), ('Winter', 2), ('Spring', 3),
('Summer', 4), ('Spring', 5), ('Summer', 6), ('Winter', 7);

-- Illustrative placeholders, deliberately not current immigration guidance.
INSERT INTO VISAREQUIREMENT VALUES
('GB', 'Demo visa information', 'Sample only. Verify entry rules with official authorities for your nationality and purpose of travel.', 0),
('JP', 'Demo visa information', 'Sample only. Verify entry rules with official authorities for your nationality and purpose of travel.', 0),
('US', 'Demo visa information', 'Sample only. Verify entry rules with official authorities for your nationality and purpose of travel.', 0),
('FR', 'Demo visa information', 'Sample only. Verify entry rules with official authorities for your nationality and purpose of travel.', 0),
('TR', 'Demo visa information', 'Sample only. Verify entry rules with official authorities for your nationality and purpose of travel.', 0),
('TH', 'Demo visa information', 'Sample only. Verify entry rules with official authorities for your nationality and purpose of travel.', 0),
('AE', 'Demo visa information', 'Sample only. Verify entry rules with official authorities for your nationality and purpose of travel.', 0);

INSERT INTO RECOMMENDATION VALUES
(1, 1, 'Activity',   'Visit the Burj Khalifa and Dubai Mall.', 95),
(2, 2, 'Sightseeing','Explore the British Museum and Buckingham Palace.', 90),
(3, 3, 'Culture',    'Visit Senso-ji temple during cherry blossom season.', 88);
